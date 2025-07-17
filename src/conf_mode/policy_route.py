#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

from json import loads
from sys import exit

from vyos.base import Warning
from vyos.config import Config
from vyos.configdiff import get_config_diff, Diff
from vyos.template import render
from vyos.utils.dict import dict_search_args
from vyos.utils.dict import dict_search_recursive
from vyos.utils.process import cmd
from vyos.utils.process import run
from vyos.utils.network import get_vrf_tableid
from vyos.defaults import rt_global_table
from vyos.defaults import rt_global_vrf
from vyos.firewall import geoip_update
from vyos import ConfigError
from vyos import airbag
airbag.enable()

mark_offset = 0x7FFFFFFF
nftables_conf = '/run/nftables_policy.conf'

valid_groups = [
    'address_group',
    'domain_group',
    'network_group',
    'port_group',
    'interface_group'
]

def geoip_updated(conf, policy):
    diff = get_config_diff(conf)
    node_diff = diff.get_child_nodes_diff(['policy'], expand_nodes=Diff.DELETE, recursive=True)

    out = {
        'name': [],
        'ipv6_name': [],
        'deleted_name': [],
        'deleted_ipv6_name': []
    }
    updated = False

    for key, path in dict_search_recursive(policy, 'geoip'):
        set_name = f'GEOIP_CC_{path[0]}_{path[1]}_{path[3]}'
        if (path[0] == 'route'):
            out['name'].append(set_name)
        elif (path[0] == 'route6'):
            set_name = f'GEOIP_CC6_{path[0]}_{path[1]}_{path[3]}'
            out['ipv6_name'].append(set_name)

        updated = True

    if 'delete' in node_diff:
        for key, path in dict_search_recursive(node_diff['delete'], 'geoip'):
            set_name = f'GEOIP_CC_{path[0]}_{path[1]}_{path[3]}'
            if (path[0] == 'route'):
                out['deleted_name'].append(set_name)
            elif (path[0] == 'route6'):
                set_name = f'GEOIP_CC6_{path[0]}_{path[1]}_{path[3]}'
                out['deleted_ipv6_name'].append(set_name)
            updated = True

    if updated:
        return out

    return False

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['policy']

    policy = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

    policy['firewall_group'] = conf.get_config_dict(['firewall', 'group'], key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

    # Remove dynamic firewall groups if present:
    if 'dynamic_group' in policy['firewall_group']:
        del policy['firewall_group']['dynamic_group']

    policy['geoip_updated'] = geoip_updated(conf, policy)
    return policy

def verify_rule(policy, name, rule_conf, ipv6, rule_id):
    icmp = 'icmp' if not ipv6 else 'icmpv6'
    if icmp in rule_conf:
        icmp_defined = False
        if 'type_name' in rule_conf[icmp]:
            icmp_defined = True
            if 'code' in rule_conf[icmp] or 'type' in rule_conf[icmp]:
                raise ConfigError(f'{name} rule {rule_id}: Cannot use ICMP type/code with ICMP type-name')
        if 'code' in rule_conf[icmp]:
            icmp_defined = True
            if 'type' not in rule_conf[icmp]:
                raise ConfigError(f'{name} rule {rule_id}: ICMP code can only be defined if ICMP type is defined')
        if 'type' in rule_conf[icmp]:
            icmp_defined = True

        if icmp_defined and 'protocol' not in rule_conf or rule_conf['protocol'] != icmp:
            raise ConfigError(f'{name} rule {rule_id}: ICMP type/code or type-name can only be defined if protocol is ICMP')

    if 'set' in rule_conf:
        if 'tcp_mss' in rule_conf['set']:
            tcp_flags = dict_search_args(rule_conf, 'tcp', 'flags')
            if not tcp_flags or 'syn' not in tcp_flags:
                raise ConfigError(f'{name} rule {rule_id}: TCP SYN flag must be set to modify TCP-MSS')

        if 'vrf' in rule_conf['set'] and 'table' in rule_conf['set']:
            raise ConfigError(f'{name} rule {rule_id}: Cannot set both forwarding route table and VRF')

    tcp_flags = dict_search_args(rule_conf, 'tcp', 'flags')
    if tcp_flags:
        if dict_search_args(rule_conf, 'protocol') != 'tcp':
            raise ConfigError('Protocol must be tcp when specifying tcp flags')

        not_flags = dict_search_args(rule_conf, 'tcp', 'flags', 'not')
        if not_flags:
            duplicates = [flag for flag in tcp_flags if flag in not_flags]
            if duplicates:
                raise ConfigError(f'Cannot match a tcp flag as set and not set')

    for side in ['destination', 'source']:
        if side in rule_conf:
            side_conf = rule_conf[side]

            if 'group' in side_conf:
                if len({'address_group', 'domain_group', 'network_group'} & set(side_conf['group'])) > 1:
                    raise ConfigError('Only one address-group, domain-group or network-group can be specified')

                for group in valid_groups:
                    if group in side_conf['group']:
                        group_name = side_conf['group'][group]

                        if group_name.startswith('!'):
                            group_name = group_name[1:]

                        fw_group = f'ipv6_{group}' if ipv6 and group in ['address_group', 'network_group'] else group
                        error_group = fw_group.replace("_", "-")
                        group_obj = dict_search_args(policy['firewall_group'], fw_group, group_name)

                        if group_obj is None:
                            raise ConfigError(f'Invalid {error_group} "{group_name}" on policy route rule')

                        if not group_obj:
                            Warning(f'{error_group} "{group_name}" has no members')

            if 'port' in side_conf or dict_search_args(side_conf, 'group', 'port_group'):
                if 'protocol' not in rule_conf:
                    raise ConfigError('Protocol must be defined if specifying a port or port-group')

                if rule_conf['protocol'] not in ['tcp', 'udp', 'tcp_udp']:
                    raise ConfigError('Protocol must be tcp, udp, or tcp_udp when specifying a port or port-group')

def verify(policy):
    for route in ['route', 'route6']:
        ipv6 = route == 'route6'
        if route in policy:
            for name, pol_conf in policy[route].items():
                if 'rule' in pol_conf:
                    for rule_id, rule_conf in pol_conf['rule'].items():
                        verify_rule(policy, name, rule_conf, ipv6, rule_id)

    return None

def generate(policy):
    if not os.path.exists(nftables_conf):
        policy['first_install'] = True

    render(nftables_conf, 'firewall/nftables-policy.j2', policy)
    return None

def apply_table_marks(policy):
    for route in ['route', 'route6']:
        if route in policy:
            cmd_str = 'ip' if route == 'route' else 'ip -6'
            tables = []
            for name, pol_conf in policy[route].items():
                if 'rule' in pol_conf:
                    for rule_id, rule_conf in pol_conf['rule'].items():
                        vrf_table_id = None
                        set_table = dict_search_args(rule_conf, 'set', 'table')
                        set_vrf = dict_search_args(rule_conf, 'set', 'vrf')
                        if set_vrf:
                            if set_vrf == 'default':
                                vrf_table_id = rt_global_vrf
                            else:
                                vrf_table_id = get_vrf_tableid(set_vrf)
                        elif set_table:
                            if set_table == 'main':
                                vrf_table_id = rt_global_table
                            else:
                                vrf_table_id = set_table
                        if vrf_table_id is not None:
                            vrf_table_id = int(vrf_table_id)
                            if vrf_table_id in tables:
                                continue
                            tables.append(vrf_table_id)
                            table_mark = mark_offset - vrf_table_id
                            cmd(f'{cmd_str} rule add pref {vrf_table_id} fwmark {table_mark} table {vrf_table_id}')

def cleanup_table_marks():
    for cmd_str in ['ip', 'ip -6']:
        json_rules = cmd(f'{cmd_str} -j -N rule list')
        rules = loads(json_rules)
        for rule in rules:
            if 'fwmark' not in rule or 'table' not in rule:
                continue
            fwmark = rule['fwmark']
            table = int(rule['table'])
            if fwmark[:2] == '0x':
                fwmark = int(fwmark, 16)
            if (int(fwmark) == (mark_offset - table)):
                cmd(f'{cmd_str} rule del fwmark {fwmark} table {table}')

def apply(policy):
    install_result = run(f'nft --file {nftables_conf}')
    if install_result == 1:
        raise ConfigError('Failed to apply policy based routing')

    if 'first_install' not in policy:
        cleanup_table_marks()

    apply_table_marks(policy)

    if policy['geoip_updated']:
        # Call helper script to Update set contents
        if 'name' in policy['geoip_updated'] or 'ipv6_name' in policy['geoip_updated']:
            print('Updating GeoIP. Please wait...')
            geoip_update(policy=policy)

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
