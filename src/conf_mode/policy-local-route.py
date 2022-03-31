#!/usr/bin/env python3
#
# Copyright (C) 2020-2021 VyOS maintainers and contributors
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os

from sys import exit

from netifaces import interfaces
from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configdict import node_changed
from vyos.configdict import leaf_node_changed
from vyos.template import render
from vyos.util import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()


def get_config(config=None):

    if config:
        conf = config
    else:
        conf = Config()
    base = ['policy']

    pbr = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    for route in ['local_route', 'local_route6']:
        dict_id = 'rule_remove' if route == 'local_route' else 'rule6_remove'
        route_key = 'local-route' if route == 'local_route' else 'local-route6'
        base_rule = base + [route_key, 'rule']

        # delete policy local-route
        dict = {}
        tmp = node_changed(conf, base_rule, key_mangling=('-', '_'))
        if tmp:
            for rule in (tmp or []):
                src = leaf_node_changed(conf, base_rule + [rule, 'source'])
                fwmk = leaf_node_changed(conf, base_rule + [rule, 'fwmark'])
                iif = leaf_node_changed(conf, base_rule + [rule, 'inbound-interface'])
                dst = leaf_node_changed(conf, base_rule + [rule, 'destination'])
                rule_def = {}
                if src:
                    rule_def = dict_merge({'source' : src}, rule_def)
                if fwmk:
                    rule_def = dict_merge({'fwmark' : fwmk}, rule_def)
                if iif:
                    rule_def = dict_merge({'inbound_interface' : iif}, rule_def)
                if dst:
                    rule_def = dict_merge({'destination' : dst}, rule_def)
                dict = dict_merge({dict_id : {rule : rule_def}}, dict)
                pbr.update(dict)

        if not route in pbr:
            continue

        # delete policy local-route rule x source x.x.x.x
        # delete policy local-route rule x fwmark x
        # delete policy local-route rule x destination x.x.x.x
        if 'rule' in pbr[route]:
            for rule, rule_config in pbr[route]['rule'].items():
                src = leaf_node_changed(conf, base_rule + [rule, 'source'])
                fwmk = leaf_node_changed(conf, base_rule + [rule, 'fwmark'])
                iif = leaf_node_changed(conf, base_rule + [rule, 'inbound-interface'])
                dst = leaf_node_changed(conf, base_rule + [rule, 'destination'])
                # keep track of changes in configuration
                # otherwise we might remove an existing node although nothing else has changed
                changed = False

                rule_def = {}
                # src is None if there are no changes to src
                if src is None:
                    # if src hasn't changed, include it in the removal selector
                    # if a new selector is added, we have to remove all previous rules without this selector
                    # to make sure we remove all previous rules with this source(s), it will be included
                    if 'source' in rule_config:
                        rule_def = dict_merge({'source': rule_config['source']}, rule_def)
                else:
                    # if src is not None, it's previous content will be returned
                    # this can be an empty array if it's just being set, or the previous value
                    # either way, something has to be changed and we only want to remove previous values
                    changed = True
                    # set the old value for removal if it's not empty
                    if len(src) > 0:
                        rule_def = dict_merge({'source' : src}, rule_def)
                if fwmk is None:
                    if 'fwmark' in rule_config:
                        rule_def = dict_merge({'fwmark': rule_config['fwmark']}, rule_def)
                else:
                    changed = True
                    if len(fwmk) > 0:
                        rule_def = dict_merge({'fwmark' : fwmk}, rule_def)
                if iif is None:
                    if 'inbound_interface' in rule_config:
                        rule_def = dict_merge({'inbound_interface': rule_config['inbound_interface']}, rule_def)
                else:
                    changed = True
                    if len(iif) > 0:
                        rule_def = dict_merge({'inbound_interface' : iif}, rule_def)
                if dst is None:
                    if 'destination' in rule_config:
                        rule_def = dict_merge({'destination': rule_config['destination']}, rule_def)
                else:
                    changed = True
                    if len(dst) > 0:
                        rule_def = dict_merge({'destination' : dst}, rule_def)
                if changed:
                    dict = dict_merge({dict_id : {rule : rule_def}}, dict)
                    pbr.update(dict)

    return pbr

def verify(pbr):
    # bail out early - looks like removal from running config
    if not pbr:
        return None

    for route in ['local_route', 'local_route6']:
        if not route in pbr:
            continue

        pbr_route = pbr[route]
        if 'rule' in pbr_route:
            for rule in pbr_route['rule']:
                if 'source' not in pbr_route['rule'][rule] \
                        and 'destination' not in pbr_route['rule'][rule] \
                        and 'fwmark' not in pbr_route['rule'][rule] \
                        and 'inbound_interface' not in pbr_route['rule'][rule]:
                    raise ConfigError('Source or destination address or fwmark or inbound-interface is required!')
                else:
                    if 'set' not in pbr_route['rule'][rule] or 'table' not in pbr_route['rule'][rule]['set']:
                        raise ConfigError('Table set is required!')
                    if 'inbound_interface' in pbr_route['rule'][rule]:
                        interface = pbr_route['rule'][rule]['inbound_interface']
                        if interface not in interfaces():
                            raise ConfigError(f'Interface "{interface}" does not exist')

    return None

def generate(pbr):
    if not pbr:
        return None

    return None

def apply(pbr):
    if not pbr:
        return None

    # Delete old rule if needed
    for rule_rm in ['rule_remove', 'rule6_remove']:
        if rule_rm in pbr:
            v6 = " -6" if rule_rm == 'rule6_remove' else ""
            for rule, rule_config in pbr[rule_rm].items():
                rule_config['source'] = rule_config['source'] if 'source' in rule_config else ['']
                for src in rule_config['source']:
                    f_src = '' if src == '' else f' from {src} '
                    rule_config['destination'] = rule_config['destination'] if 'destination' in rule_config else ['']
                    for dst in rule_config['destination']:
                        f_dst = '' if dst == '' else f' to {dst} '
                        rule_config['fwmark'] = rule_config['fwmark'] if 'fwmark' in rule_config else ['']
                        for fwmk in rule_config['fwmark']:
                            f_fwmk = '' if fwmk == '' else f' fwmark {fwmk} '
                            rule_config['inbound_interface'] = rule_config['inbound_interface'] if 'inbound_interface' in rule_config else ['']
                            for iif in rule_config['inbound_interface']:
                                f_iif = '' if iif == '' else f' iif {iif} '
                                call(f'ip{v6} rule del prio {rule} {f_src}{f_dst}{f_fwmk}{f_iif}')

    # Generate new config
    for route in ['local_route', 'local_route6']:
        if not route in pbr:
            continue

        v6 = " -6" if route == 'local_route6' else ""

        pbr_route = pbr[route]
        if 'rule' in pbr_route:
            for rule, rule_config in pbr_route['rule'].items():
                table = rule_config['set']['table']

                rule_config['source'] = rule_config['source'] if 'source' in rule_config else ['all']
                for src in rule_config['source'] or ['all']:
                    f_src = '' if src == '' else f' from {src} '
                    rule_config['destination'] = rule_config['destination'] if 'destination' in rule_config else ['all']
                    for dst in rule_config['destination']:
                        f_dst = '' if dst == '' else f' to {dst} '
                        f_fwmk = ''
                        if 'fwmark' in rule_config:
                            fwmk = rule_config['fwmark']
                            f_fwmk = f' fwmark {fwmk} '
                        f_iif = ''
                        if 'inbound_interface' in rule_config:
                            iif = rule_config['inbound_interface']
                            f_iif = f' iif {iif} '
                        call(f'ip{v6} rule add prio {rule} {f_src}{f_dst}{f_fwmk}{f_iif} lookup {table}')

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
