#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
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

from sys import exit
from netifaces import interfaces

from vyos.base import Warning
from vyos.config import Config
from vyos.configdep import set_dependents
from vyos.configdep import call_dependents
from vyos.configdict import dict_merge
from vyos.configverify import verify_interface_exists
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
from vyos.utils.dict import dict_search_recursive
from vyos.utils.process import run
from vyos import ConfigError
from vyos import airbag
from vyos.xml_ref import relative_defaults


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


def _clean_conf_dict(conf):
    """
    Delete empty nodes from config e.g.
        match ADDRESS30 {
            ip {
                source {}
            }
        }
    """
    if isinstance(conf, dict):
        return {node: _clean_conf_dict(val) for node, val in conf.items() if val != {} and _clean_conf_dict(val) != {}}
    else:
        return conf


def _get_group_filters(config: dict, group_name: str, visited=None) -> dict:
    filters = dict()
    if not visited:
        visited = [group_name, ]
    else:
        if group_name in visited:
            return filters
        visited.append(group_name)

    for filter, filter_config in config.get(group_name, {}).items():
        if filter == 'match':
            for match, match_config in filter_config.items():
               filters[f'{group_name}-{match}'] = match_config
        elif filter == 'match_group':
            for group in filter_config:
                filters.update(_get_group_filters(config, group, visited))

    return filters


def _get_group_match(config:dict, group_name:str) -> dict:
    match = dict()
    for key, val in _get_group_filters(config, group_name).items():
        # delete duplicate matches
        if val not in match.values():
            match[key] = val

    return match


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

    for ifname in interfaces():
        if_node = Section.get_config_path(ifname)

        if not if_node:
            continue

        path = f'interfaces {if_node}'
        if conf.exists(f'{path} mirror') or conf.exists(f'{path} redirect'):
            type_node = path.split(" ")[1] # return only interface type node
            set_dependents(type_node, conf, ifname.split(".")[0])

    for policy in qos.get('policy', []):
        if policy in ['random_detect']:
            for rd_name in list(qos['policy'][policy]):
                # There are eight precedence levels - ensure all are present
                # to be filled later down with the appropriate default values
                default_p_val = relative_defaults(
                    ['qos', 'policy', 'random-detect', rd_name, 'precedence'],
                    {'precedence': {'0': {}}},
                    get_first_key=True, recursive=True
                )['0']
                default_p_val = {key.replace('-', '_'): value for key, value in default_p_val.items()}
                default_precedence = {
                    'precedence': {'0': default_p_val, '1': default_p_val,
                                   '2': default_p_val, '3': default_p_val,
                                   '4': default_p_val, '5': default_p_val,
                                   '6': default_p_val, '7': default_p_val}}

                qos['policy']['random_detect'][rd_name] = dict_merge(
                    default_precedence, qos['policy']['random_detect'][rd_name])

    qos = conf.merge_defaults(qos, recursive=True)

    if 'traffic_match_group' in qos:
        for group, group_config in qos['traffic_match_group'].items():
            if 'match_group' in group_config:
                qos['traffic_match_group'][group]['match'] = _get_group_match(qos['traffic_match_group'], group)

    for policy in qos.get('policy', []):
        for p_name, p_config in qos['policy'][policy].items():
            # cleanup empty match config
            if 'class' in p_config:
                for cls, cls_config in p_config['class'].items():
                    if 'match_group' in cls_config:
                        # merge group match to match
                        for group in cls_config['match_group']:
                            for match, match_conf in qos['traffic_match_group'].get(group, {'match': {}})['match'].items():
                                if 'match' not in cls_config:
                                    cls_config['match'] = dict()
                                if match in cls_config['match']:
                                    cls_config['match'][f'{group}-{match}'] = match_conf
                                else:
                                    cls_config['match'][match] = match_conf

                    if 'match' in cls_config:
                        cls_config['match'] = _clean_conf_dict(cls_config['match'])
                        if cls_config['match'] == {}:
                            del cls_config['match']

    return qos


def _verify_match(cls_config: dict) -> None:
    if 'match' in cls_config:
        for match, match_config in cls_config['match'].items():
            if {'ip', 'ipv6'} <= set(match_config):
                raise ConfigError(
                    f'Can not use both IPv6 and IPv4 in one match ({match})!')


def _verify_match_group_exist(cls_config, qos):
    if 'match_group' in cls_config:
        for group in cls_config['match_group']:
            if 'traffic_match_group' not in qos or group not in qos['traffic_match_group']:
                Warning(f'Match group "{group}" does not exist!')


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
                        if 'bandwidth' not in cls_config and policy_type not in ['priority_queue', 'round_robin', 'shaper_hfsc']:
                            raise ConfigError(f'Bandwidth must be defined for policy "{policy}" class "{cls}"!')
                        _verify_match(cls_config)
                        _verify_match_group_exist(cls_config, qos)
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
                if policy_type in ['priority_queue']:
                    if 'default' not in policy_config:
                        raise ConfigError(f'Policy {policy} misses "default" class!')
                if 'default' in policy_config:
                    if 'bandwidth' not in policy_config['default'] and policy_type not in ['priority_queue', 'round_robin', 'shaper_hfsc']:
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

    if 'traffic_match_group' in qos:
        for group, group_config in qos['traffic_match_group'].items():
            _verify_match(group_config)
            _verify_match_group_exist(group_config, qos)

    return None


def generate(qos):
    if not qos or 'interface' not in qos:
        return None

    return None

def apply(qos):
    # Always delete "old" shapers first
    for interface in interfaces():
        # Ignore errors (may have no qdisc)
        run(f'tc qdisc del dev {interface} parent ffff:')
        run(f'tc qdisc del dev {interface} root')

    call_dependents()

    if not qos or 'interface' not in qos:
        return None

    for interface, interface_config in qos['interface'].items():
        if not verify_interface_exists(interface, warning_only=True):
            # When shaper is bound to a dialup (e.g. PPPoE) interface it is
            # possible that it is yet not availbale when to QoS code runs.
            # Skip the configuration and inform the user via warning_only=True
            continue

        for direction in ['egress', 'ingress']:
            # bail out early if shaper for given direction is not used at all
            if direction not in interface_config:
                continue

            shaper_type, shaper_config = get_shaper(qos, interface_config, direction)
            tmp = shaper_type(interface)
            tmp.update(shaper_config, direction)

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
