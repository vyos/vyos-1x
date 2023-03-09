#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import os

from sys import exit
from netifaces import interfaces

from vyos.base import Warning
from vyos.config import Config
from vyos.configdep import set_dependents, call_dependents
from vyos.configdict import dict_merge
from vyos.ifconfig import Section
from vyos.qos import CAKE
from vyos.qos import DropTail
from vyos.qos import FairQueue
from vyos.qos import FQCodel
from vyos.qos import Limiter
from vyos.qos import NetEm
from vyos.qos import Priority
from vyos.qos import RandomDetect
from vyos.qos import RateLimiter
from vyos.qos import RoundRobin
from vyos.qos import TrafficShaper
from vyos.qos import TrafficShaperHFSC
from vyos.util import call
from vyos.util import dict_search_recursive
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

map_vyops_tc = {
    'cake'             : CAKE,
    'drop_tail'        : DropTail,
    'fair_queue'       : FairQueue,
    'fq_codel'         : FQCodel,
    'limiter'          : Limiter,
    'network_emulator' : NetEm,
    'priority_queue'   : Priority,
    'random_detect'    : RandomDetect,
    'rate_control'     : RateLimiter,
    'round_robin'      : RoundRobin,
    'shaper'           : TrafficShaper,
    'shaper_hfsc'      : TrafficShaperHFSC,
}

def get_shaper(qos, interface_config, direction):
    policy_name = interface_config[direction]
    # An interface might have a QoS configuration, search the used
    # configuration referenced by this. Path will hold the dict element
    # referenced by the config, as this will be of sort:
    #
    # ['policy', 'drop_tail', 'foo-dtail'] <- we are only interested in
    # drop_tail as the policy/shaper type
    _, path = next(dict_search_recursive(qos, policy_name))
    shaper_type = path[1]
    shaper_config = qos['policy'][shaper_type][policy_name]

    return (map_vyops_tc[shaper_type], shaper_config)

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['qos']
    if not conf.exists(base):
        return None

    qos = conf.get_config_dict(base, key_mangling=('-', '_'),
                               get_first_key=True,
                               no_tag_node_value_mangle=True)

    if 'interface' in qos:
        for ifname, if_conf in qos['interface'].items():
            if_node = Section.get_config_path(ifname)

            if not if_node:
                continue

            path = f'interfaces {if_node}'
            if conf.exists(f'{path} mirror') or conf.exists(f'{path} redirect'):
                type_node = path.split(" ")[1] # return only interface type node
                set_dependents(type_node, conf, ifname)

    if 'policy' in qos:
        for policy in qos['policy']:
            # when calling defaults() we need to use the real CLI node, thus we
            # need a hyphen
            policy_hyphen = policy.replace('_', '-')

            if policy in ['random_detect']:
                for rd_name, rd_config in qos['policy'][policy].items():
                    # There are eight precedence levels - ensure all are present
                    # to be filled later down with the appropriate default values
                    default_precedence = {'precedence' : { '0' : {}, '1' : {}, '2' : {}, '3' : {},
                                                           '4' : {}, '5' : {}, '6' : {}, '7' : {} }}
                    qos['policy']['random_detect'][rd_name] = dict_merge(
                        default_precedence, qos['policy']['random_detect'][rd_name])

            for p_name, p_config in qos['policy'][policy].items():
                default_values = defaults(base + ['policy', policy_hyphen])

                if policy in ['priority_queue']:
                    if 'default' not in p_config:
                        raise ConfigError(f'QoS policy {p_name} misses "default" class!')

                # XXX: T2665: we can not safely rely on the defaults() when there are
                # tagNodes in place, it is better to blend in the defaults manually.
                if 'class' in default_values:
                    del default_values['class']
                if 'precedence' in default_values:
                    del default_values['precedence']

                qos['policy'][policy][p_name] = dict_merge(
                    default_values, qos['policy'][policy][p_name])

                # class is another tag node which requires individual handling
                if 'class' in p_config:
                    default_values = defaults(base + ['policy', policy_hyphen, 'class'])
                    for p_class in p_config['class']:
                        qos['policy'][policy][p_name]['class'][p_class] = dict_merge(
                            default_values, qos['policy'][policy][p_name]['class'][p_class])

                if 'precedence' in p_config:
                    default_values = defaults(base + ['policy', policy_hyphen, 'precedence'])
                    # precedence values are a bit more complex as they are calculated
                    # under specific circumstances - thus we need to iterate two times.
                    # first blend in the defaults from XML / CLI
                    for precedence in p_config['precedence']:
                        qos['policy'][policy][p_name]['precedence'][precedence] = dict_merge(
                            default_values, qos['policy'][policy][p_name]['precedence'][precedence])
                    # second calculate defaults based on actual dictionary
                    for precedence in p_config['precedence']:
                        max_thr = int(qos['policy'][policy][p_name]['precedence'][precedence]['maximum_threshold'])
                        if 'minimum_threshold' not in qos['policy'][policy][p_name]['precedence'][precedence]:
                            qos['policy'][policy][p_name]['precedence'][precedence]['minimum_threshold'] = str(
                                int((9 + int(precedence)) * max_thr) // 18);

                        if 'queue_limit' not in qos['policy'][policy][p_name]['precedence'][precedence]:
                            qos['policy'][policy][p_name]['precedence'][precedence]['queue_limit'] = \
                                str(int(4 * max_thr))

    return qos

def verify(qos):
    if not qos or 'interface' not in qos:
        return None

    # network policy emulator
    # reorder rerquires delay to be set
    if 'policy' in qos:
        for policy_type in qos['policy']:
            for policy, policy_config in qos['policy'][policy_type].items():
                # a policy with it's given name is only allowed to exist once
                # on the system. This is because an interface selects a policy
                # for ingress/egress traffic, and thus there can only be one
                # policy with a given name.
                #
                # We check if the policy name occurs more then once - error out
                # if this is true
                counter = 0
                for _, path in dict_search_recursive(qos['policy'], policy):
                    counter += 1
                    if counter > 1:
                        raise ConfigError(f'Conflicting policy name "{policy}", already in use!')

                if 'class' in policy_config:
                    for cls, cls_config in policy_config['class'].items():
                        # bandwidth is not mandatory for priority-queue - that is why this is on the exception list
                        if 'bandwidth' not in cls_config and policy_type not in ['priority_queue', 'round_robin']:
                            raise ConfigError(f'Bandwidth must be defined for policy "{policy}" class "{cls}"!')
                    if 'match' in cls_config:
                        for match, match_config in cls_config['match'].items():
                            if {'ip', 'ipv6'} <= set(match_config):
                                 raise ConfigError(f'Can not use both IPv6 and IPv4 in one match ({match})!')

                if policy_type in ['random_detect']:
                    if 'precedence' in policy_config:
                        for precedence, precedence_config in policy_config['precedence'].items():
                            max_tr = int(precedence_config['maximum_threshold'])
                            if {'maximum_threshold', 'minimum_threshold'} <= set(precedence_config):
                                min_tr = int(precedence_config['minimum_threshold'])
                                if min_tr >= max_tr:
                                    raise ConfigError(f'Policy "{policy}" uses min-threshold "{min_tr}" >= max-threshold "{max_tr}"!')

                            if {'maximum_threshold', 'queue_limit'} <= set(precedence_config):
                                queue_lim = int(precedence_config['queue_limit'])
                                if queue_lim < max_tr:
                                    raise ConfigError(f'Policy "{policy}" uses queue-limit "{queue_lim}" < max-threshold "{max_tr}"!')

                if 'default' in policy_config:
                    if 'bandwidth' not in policy_config['default'] and policy_type not in ['priority_queue', 'round_robin']:
                        raise ConfigError('Bandwidth not defined for default traffic!')

    # we should check interface ingress/egress configuration after verifying that
    # the policy name is used only once - this makes the logic easier!
    for interface, interface_config in qos['interface'].items():
        for direction in ['egress', 'ingress']:
            # bail out early if shaper for given direction is not used at all
            if direction not in interface_config:
                continue

            policy_name = interface_config[direction]
            if 'policy' not in qos or list(dict_search_recursive(qos['policy'], policy_name)) == []:
                raise ConfigError(f'Selected QoS policy "{policy_name}" does not exist!')

            shaper_type, shaper_config = get_shaper(qos, interface_config, direction)
            tmp = shaper_type(interface).get_direction()
            if direction not in tmp:
                raise ConfigError(f'Selected QoS policy on interface "{interface}" only supports "{tmp}"!')

    return None

def generate(qos):
    if not qos or 'interface' not in qos:
        return None

    return None

def apply(qos):
    # Always delete "old" shapers first
    for interface in interfaces():
        # Ignore errors (may have no qdisc)
        call(f'tc qdisc del dev {interface} parent ffff:')
        call(f'tc qdisc del dev {interface} root')

    if not qos or 'interface' not in qos:
        return None

    for interface, interface_config in qos['interface'].items():
        if not os.path.exists(f'/sys/class/net/{interface}'):
            # When shaper is bound to a dialup (e.g. PPPoE) interface it is
            # possible that it is yet not availbale when to QoS code runs.
            # Skip the configuration and inform the user
            Warning(f'Interface "{interface}" does not exist!')
            continue

        for direction in ['egress', 'ingress']:
            # bail out early if shaper for given direction is not used at all
            if direction not in interface_config:
                continue

            shaper_type, shaper_config = get_shaper(qos, interface_config, direction)
            tmp = shaper_type(interface)
            tmp.update(shaper_config, direction)

    call_dependents()

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
