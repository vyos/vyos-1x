#!/usr/bin/env python3
#
# Copyright (C) 2020-2024 VyOS maintainers and contributors
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

from itertools import product
from sys import exit

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configdict import node_changed
from vyos.configdict import leaf_node_changed
from vyos.configverify import verify_interface_exists
from vyos.utils.process import call
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
                src = leaf_node_changed(conf, base_rule + [rule, 'source', 'address'])
                src_port = leaf_node_changed(conf, base_rule + [rule, 'source', 'port'])
                fwmk = leaf_node_changed(conf, base_rule + [rule, 'fwmark'])
                iif = leaf_node_changed(conf, base_rule + [rule, 'inbound-interface'])
                dst = leaf_node_changed(conf, base_rule + [rule, 'destination', 'address'])
                dst_port = leaf_node_changed(conf, base_rule + [rule, 'destination', 'port'])
                table = leaf_node_changed(conf, base_rule + [rule, 'set', 'table'])
                vrf = leaf_node_changed(conf, base_rule + [rule, 'set', 'vrf'])
                proto = leaf_node_changed(conf, base_rule + [rule, 'protocol'])
                rule_def = {}
                if src:
                    rule_def = dict_merge({'source': {'address': src}}, rule_def)
                if src_port:
                    rule_def = dict_merge({'source': {'port': src_port}}, rule_def)
                if fwmk:
                    rule_def = dict_merge({'fwmark' : fwmk}, rule_def)
                if iif:
                    rule_def = dict_merge({'inbound_interface' : iif}, rule_def)
                if dst:
                    rule_def = dict_merge({'destination': {'address': dst}}, rule_def)
                if dst_port:
                    rule_def = dict_merge({'destination': {'port': dst_port}}, rule_def)
                if table:
                    rule_def = dict_merge({'table' : table}, rule_def)
                if vrf:
                    rule_def = dict_merge({'vrf' : vrf}, rule_def)
                if proto:
                    rule_def = dict_merge({'protocol' : proto}, rule_def)
                dict = dict_merge({dict_id : {rule : rule_def}}, dict)
                pbr.update(dict)

        if not route in pbr:
            continue

        # delete policy local-route rule x source x.x.x.x
        # delete policy local-route rule x fwmark x
        # delete policy local-route rule x destination x.x.x.x
        if 'rule' in pbr[route]:
            for rule, rule_config in pbr[route]['rule'].items():
                src = leaf_node_changed(conf, base_rule + [rule, 'source', 'address'])
                src_port = leaf_node_changed(conf, base_rule + [rule, 'source', 'port'])
                fwmk = leaf_node_changed(conf, base_rule + [rule, 'fwmark'])
                iif = leaf_node_changed(conf, base_rule + [rule, 'inbound-interface'])
                dst = leaf_node_changed(conf, base_rule + [rule, 'destination', 'address'])
                dst_port = leaf_node_changed(conf, base_rule + [rule, 'destination', 'port'])
                table = leaf_node_changed(conf, base_rule + [rule, 'set', 'table'])
                vrf = leaf_node_changed(conf, base_rule + [rule, 'set', 'vrf'])
                proto = leaf_node_changed(conf, base_rule + [rule, 'protocol'])
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
                        if 'address' in rule_config['source']:
                            rule_def = dict_merge({'source': {'address': rule_config['source']['address']}}, rule_def)
                else:
                    # if src is not None, it's previous content will be returned
                    # this can be an empty array if it's just being set, or the previous value
                    # either way, something has to be changed and we only want to remove previous values
                    changed = True
                    # set the old value for removal if it's not empty
                    if len(src) > 0:
                        rule_def = dict_merge({'source': {'address': src}}, rule_def)

                # source port
                if src_port is None:
                    if 'source' in rule_config:
                        if 'port' in rule_config['source']:
                            tmp = rule_config['source']['port']
                            if isinstance(tmp, str):
                                tmp = [tmp]
                            rule_def = dict_merge({'source': {'port': tmp}}, rule_def)
                else:
                    changed = True
                    if len(src_port) > 0:
                        rule_def = dict_merge({'source': {'port': src_port}}, rule_def)

                # fwmark
                if fwmk is None:
                    if 'fwmark' in rule_config:
                        tmp = rule_config['fwmark']
                        if isinstance(tmp, str):
                            tmp = [tmp]
                        rule_def = dict_merge({'fwmark': tmp}, rule_def)
                else:
                    changed = True
                    if len(fwmk) > 0:
                        rule_def = dict_merge({'fwmark' : fwmk}, rule_def)

                # inbound-interface
                if iif is None:
                    if 'inbound_interface' in rule_config:
                        rule_def = dict_merge({'inbound_interface': rule_config['inbound_interface']}, rule_def)
                else:
                    changed = True
                    if len(iif) > 0:
                        rule_def = dict_merge({'inbound_interface' : iif}, rule_def)

                # destination address
                if dst is None:
                    if 'destination' in rule_config:
                        if 'address' in rule_config['destination']:
                            rule_def = dict_merge({'destination': {'address': rule_config['destination']['address']}}, rule_def)
                else:
                    changed = True
                    if len(dst) > 0:
                        rule_def = dict_merge({'destination': {'address': dst}}, rule_def)

                # destination port
                if dst_port is None:
                    if 'destination' in rule_config:
                        if 'port' in rule_config['destination']:
                            tmp = rule_config['destination']['port']
                            if isinstance(tmp, str):
                                tmp = [tmp]
                            rule_def = dict_merge({'destination': {'port': tmp}}, rule_def)
                else:
                    changed = True
                    if len(dst_port) > 0:
                        rule_def = dict_merge({'destination': {'port': dst_port}}, rule_def)

                # table
                if table is None:
                    if 'set' in rule_config and 'table' in rule_config['set']:
                        rule_def = dict_merge({'table': [rule_config['set']['table']]}, rule_def)
                else:
                    changed = True
                    if len(table) > 0:
                        rule_def = dict_merge({'table' : table}, rule_def)

                # vrf
                if vrf is None:
                    if 'set' in rule_config and 'vrf' in rule_config['set']:
                        rule_def = dict_merge({'vrf': [rule_config['set']['vrf']]}, rule_def)
                else:
                    changed = True
                    if len(vrf) > 0:
                        rule_def = dict_merge({'vrf' : vrf}, rule_def)

                # protocol
                if proto is None:
                    if 'protocol' in rule_config:
                        tmp = rule_config['protocol']
                        if isinstance(tmp, str):
                            tmp = [tmp]
                        rule_def = dict_merge({'protocol': tmp}, rule_def)
                else:
                    changed = True
                    if len(proto) > 0:
                        rule_def = dict_merge({'protocol' : proto}, rule_def)

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
                if (
                    'source' not in pbr_route['rule'][rule] and
                    'destination' not in pbr_route['rule'][rule] and
                    'fwmark' not in pbr_route['rule'][rule] and
                    'inbound_interface' not in pbr_route['rule'][rule] and
                    'protocol' not in pbr_route['rule'][rule]
                ):
                    raise ConfigError('Source or destination address or fwmark or inbound-interface or protocol is required!')

                if 'set' not in pbr_route['rule'][rule]:
                    raise ConfigError('Either set table or set vrf is required!')

                set_tgts = pbr_route['rule'][rule]['set']
                if 'table' not in set_tgts and 'vrf' not in set_tgts:
                    raise ConfigError('Either set table or set vrf is required!')

                if 'table' in set_tgts and 'vrf' in set_tgts:
                    raise ConfigError('set table and set vrf cannot both be set!')

                if 'inbound_interface' in pbr_route['rule'][rule]:
                    interface = pbr_route['rule'][rule]['inbound_interface']
                    verify_interface_exists(pbr, interface)

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
                source = rule_config.get('source', {}).get('address', [''])
                source_port = rule_config.get('source', {}).get('port', [''])
                destination = rule_config.get('destination', {}).get('address', [''])
                destination_port = rule_config.get('destination', {}).get('port', [''])
                fwmark = rule_config.get('fwmark', [''])
                inbound_interface = rule_config.get('inbound_interface', [''])
                protocol = rule_config.get('protocol', [''])
                # VRF 'default' is actually table 'main' for RIB rules
                vrf = [ 'main' if x == 'default' else x for x in rule_config.get('vrf', ['']) ]
                # See generate section below for table/vrf overlap explanation 
                table_or_vrf = rule_config.get('table', vrf)

                for src, dst, src_port, dst_port, fwmk, iif, proto, table_or_vrf in product(
                        source, destination, source_port, destination_port,
                        fwmark, inbound_interface, protocol, table_or_vrf):
                    f_src = '' if src == '' else f' from {src} '
                    f_src_port = '' if src_port == '' else f' sport {src_port} '
                    f_dst = '' if dst == '' else f' to {dst} '
                    f_dst_port = '' if dst_port == '' else f' dport {dst_port} '
                    f_fwmk = '' if fwmk == '' else f' fwmark {fwmk} '
                    f_iif = '' if iif == '' else f' iif {iif} '
                    f_proto = '' if proto == '' else f' ipproto {proto} '
                    f_table = '' if table_or_vrf == '' else f' lookup {table_or_vrf} '

                    call(f'ip{v6} rule del prio {rule} {f_src}{f_dst}{f_proto}{f_src_port}{f_dst_port}{f_fwmk}{f_iif}{f_table}')

    # Generate new config
    for route in ['local_route', 'local_route6']:
        if not route in pbr:
            continue

        v6 = " -6" if route == 'local_route6' else ""
        pbr_route = pbr[route]

        if 'rule' in pbr_route:
            for rule, rule_config in pbr_route['rule'].items():
                # VRFs get configred as route table alias names for iproute2 and only 
                # one 'set' can get past validation. Either can be fed to lookup. 
                vrf = rule_config['set'].get('vrf', '')
                if vrf == 'default':
                    table_or_vrf = 'main'
                else:
                    table_or_vrf = rule_config['set'].get('table', vrf)
                source = rule_config.get('source', {}).get('address', ['all'])
                source_port = rule_config.get('source', {}).get('port', '')
                destination = rule_config.get('destination', {}).get('address', ['all'])
                destination_port = rule_config.get('destination', {}).get('port', '')
                fwmark = rule_config.get('fwmark', '')
                inbound_interface = rule_config.get('inbound_interface', '')
                protocol = rule_config.get('protocol', '')

                for src in source:
                    f_src = f' from {src} ' if src else ''
                    for dst in destination:
                        f_dst = f' to {dst} ' if dst else ''
                        f_src_port = f' sport {source_port} ' if source_port else ''
                        f_dst_port = f' dport {destination_port} ' if destination_port else ''
                        f_fwmk = f' fwmark {fwmark} ' if fwmark else ''
                        f_iif = f' iif {inbound_interface} ' if inbound_interface else ''
                        f_proto = f' ipproto {protocol} ' if protocol else ''

                        call(f'ip{v6} rule add prio {rule}{f_src}{f_dst}{f_proto}{f_src_port}{f_dst_port}{f_fwmk}{f_iif} lookup {table_or_vrf}')

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
