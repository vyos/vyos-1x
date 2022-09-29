#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import ipaddress
import json
import re
import tabulate

from vyos.config import Config
from vyos.util import cmd
from vyos.util import dict_search_args

def get_firewall_interfaces(firewall, name=None, ipv6=False):
    directions = ['in', 'out', 'local']

    if 'interface' in firewall:
        for ifname, if_conf in firewall['interface'].items():
            for direction in directions:
                if direction not in if_conf:
                    continue

                fw_conf = if_conf[direction]
                name_str = f'({ifname},{direction})'

                if 'name' in fw_conf:
                    fw_name = fw_conf['name']

                    if not name:
                        firewall['name'][fw_name]['interface'].append(name_str)
                    elif not ipv6 and name == fw_name:
                        firewall['interface'].append(name_str)

                if 'ipv6_name' in fw_conf:
                    fw_name = fw_conf['ipv6_name']

                    if not name:
                        firewall['ipv6_name'][fw_name]['interface'].append(name_str)
                    elif ipv6 and name == fw_name:
                        firewall['interface'].append(name_str)

    return firewall

def get_config_firewall(conf, name=None, ipv6=False, interfaces=True):
    config_path = ['firewall']
    if name:
        config_path += ['ipv6-name' if ipv6 else 'name', name]

    firewall = conf.get_config_dict(config_path, key_mangling=('-', '_'),
                                get_first_key=True, no_tag_node_value_mangle=True)
    if firewall and interfaces:
        if name:
            firewall['interface'] = []
        else:
            if 'name' in firewall:
                for fw_name, name_conf in firewall['name'].items():
                    name_conf['interface'] = []

            if 'ipv6_name' in firewall:
                for fw_name, name_conf in firewall['ipv6_name'].items():
                    name_conf['interface'] = []

        get_firewall_interfaces(firewall, name, ipv6)
    return firewall

def get_nftables_details(name, ipv6=False):
    suffix = '6' if ipv6 else ''
    name_prefix = 'NAME6_' if ipv6 else 'NAME_'
    command = f'sudo nft list chain ip{suffix} vyos_filter {name_prefix}{name}'
    try:
        results = cmd(command)
    except:
        return {}

    out = {}
    for line in results.split('\n'):
        comment_search = re.search(rf'{name}[\- ](\d+|default-action)', line)
        if not comment_search:
            continue

        rule = {}
        rule_id = comment_search[1]
        counter_search = re.search(r'counter packets (\d+) bytes (\d+)', line)
        if counter_search:
            rule['packets'] = counter_search[1]
            rule['bytes'] = counter_search[2]

        rule['conditions'] = re.sub(r'(\b(counter packets \d+ bytes \d+|drop|reject|return|log)\b|comment "[\w\-]+")', '', line).strip()
        out[rule_id] = rule
    return out

def output_firewall_name(name, name_conf, ipv6=False, single_rule_id=None):
    ip_str = 'IPv6' if ipv6 else 'IPv4'
    print(f'\n---------------------------------\n{ip_str} Firewall "{name}"\n')

    if name_conf['interface']:
        print('Active on: {0}\n'.format(" ".join(name_conf['interface'])))

    details = get_nftables_details(name, ipv6)
    rows = []

    if 'rule' in name_conf:
        for rule_id, rule_conf in name_conf['rule'].items():
            if single_rule_id and rule_id != single_rule_id:
                continue

            if 'disable' in rule_conf:
                continue

            row = [rule_id, rule_conf['action'], rule_conf['protocol'] if 'protocol' in rule_conf else 'all']
            if rule_id in details:
                rule_details = details[rule_id]
                row.append(rule_details.get('packets', 0))
                row.append(rule_details.get('bytes', 0))
                row.append(rule_details['conditions'])
            rows.append(row)

    if 'default_action' in name_conf and not single_rule_id:
        row = ['default', name_conf['default_action'], 'all']
        if 'default-action' in details:
            rule_details = details['default-action']
            row.append(rule_details.get('packets', 0))
            row.append(rule_details.get('bytes', 0))
        rows.append(row)

    if rows:
        header = ['Rule', 'Action', 'Protocol', 'Packets', 'Bytes', 'Conditions']
        print(tabulate.tabulate(rows, header) + '\n')

def output_firewall_name_statistics(name, name_conf, ipv6=False, single_rule_id=None):
    ip_str = 'IPv6' if ipv6 else 'IPv4'
    print(f'\n---------------------------------\n{ip_str} Firewall "{name}"\n')

    if name_conf['interface']:
        print('Active on: {0}\n'.format(" ".join(name_conf['interface'])))

    details = get_nftables_details(name, ipv6)
    rows = []

    if 'rule' in name_conf:
        for rule_id, rule_conf in name_conf['rule'].items():
            if single_rule_id and rule_id != single_rule_id:
                continue

            if 'disable' in rule_conf:
                continue

            source_addr = dict_search_args(rule_conf, 'source', 'address') or '0.0.0.0/0'
            dest_addr = dict_search_args(rule_conf, 'destination', 'address') or '0.0.0.0/0'

            row = [rule_id]
            if rule_id in details:
                rule_details = details[rule_id]
                row.append(rule_details.get('packets', 0))
                row.append(rule_details.get('bytes', 0))
            else:
                row.append('0')
                row.append('0')
            row.append(rule_conf['action'])
            row.append(source_addr)
            row.append(dest_addr)
            rows.append(row)

    if 'default_action' in name_conf and not single_rule_id:
        row = ['default']
        if 'default-action' in details:
            rule_details = details['default-action']
            row.append(rule_details.get('packets', 0))
            row.append(rule_details.get('bytes', 0))
        else:
            row.append('0')
            row.append('0')
        row.append(name_conf['default_action'])
        row.append('0.0.0.0/0') # Source
        row.append('0.0.0.0/0') # Dest
        rows.append(row)

    if rows:
        header = ['Rule', 'Packets', 'Bytes', 'Action', 'Source', 'Destination']
        print(tabulate.tabulate(rows, header) + '\n')

def show_firewall():
    print('Rulesets Information')

    conf = Config()
    firewall = get_config_firewall(conf)

    if not firewall:
        return

    if 'name' in firewall:
        for name, name_conf in firewall['name'].items():
            output_firewall_name(name, name_conf, ipv6=False)

    if 'ipv6_name' in firewall:
        for name, name_conf in firewall['ipv6_name'].items():
            output_firewall_name(name, name_conf, ipv6=True)

def show_firewall_name(name, ipv6=False):
    print('Ruleset Information')

    conf = Config()
    firewall = get_config_firewall(conf, name, ipv6)
    if firewall:
        output_firewall_name(name, firewall, ipv6)

def show_firewall_rule(name, rule_id, ipv6=False):
    print('Rule Information')

    conf = Config()
    firewall = get_config_firewall(conf, name, ipv6)
    if firewall:
        output_firewall_name(name, firewall, ipv6, rule_id)

def show_firewall_group(name=None):
    conf = Config()
    firewall = get_config_firewall(conf, interfaces=False)

    if 'group' not in firewall:
        return

    def find_references(group_type, group_name):
        out = []
        for name_type in ['name', 'ipv6_name']:
            if name_type not in firewall:
                continue
            for name, name_conf in firewall[name_type].items():
                if 'rule' not in name_conf:
                    continue
                for rule_id, rule_conf in name_conf['rule'].items():
                    source_group = dict_search_args(rule_conf, 'source', 'group', group_type)
                    dest_group = dict_search_args(rule_conf, 'destination', 'group', group_type)
                    if source_group and group_name == source_group:
                        out.append(f'{name}-{rule_id}')
                    elif dest_group and group_name == dest_group:
                        out.append(f'{name}-{rule_id}')
        return out

    header = ['Name', 'Type', 'References', 'Members']
    rows = []

    for group_type, group_type_conf in firewall['group'].items():
        for group_name, group_conf in group_type_conf.items():
            if name and name != group_name:
                continue

            references = find_references(group_type, group_name)
            row = [group_name, group_type, '\n'.join(references) or 'N/A']
            if 'address' in group_conf:
                row.append("\n".join(sorted(group_conf['address'])))
            elif 'network' in group_conf:
                row.append("\n".join(sorted(group_conf['network'], key=ipaddress.ip_network)))
            elif 'mac_address' in group_conf:
                row.append("\n".join(sorted(group_conf['mac_address'])))
            elif 'port' in group_conf:
                row.append("\n".join(sorted(group_conf['port'])))
            else:
                row.append('N/A')
            rows.append(row)

    if rows:
        print('Firewall Groups\n')
        print(tabulate.tabulate(rows, header))

def show_summary():
    print('Ruleset Summary')

    conf = Config()
    firewall = get_config_firewall(conf)

    if not firewall:
        return

    header = ['Ruleset Name', 'Description', 'References']
    v4_out = []
    v6_out = []

    if 'name' in firewall:
        for name, name_conf in firewall['name'].items():
            description = name_conf.get('description', '')
            interfaces = ", ".join(name_conf['interface'])
            v4_out.append([name, description, interfaces])

    if 'ipv6_name' in firewall:
        for name, name_conf in firewall['ipv6_name'].items():
            description = name_conf.get('description', '')
            interfaces = ", ".join(name_conf['interface'])
            v6_out.append([name, description, interfaces or 'N/A'])

    if v6_out:
        print('\nIPv6 name:\n')
        print(tabulate.tabulate(v6_out, header) + '\n')

    if v4_out:
        print('\nIPv4 name:\n')
        print(tabulate.tabulate(v4_out, header) + '\n')

    show_firewall_group()

def show_statistics():
    print('Rulesets Statistics')

    conf = Config()
    firewall = get_config_firewall(conf)

    if not firewall:
        return

    if 'name' in firewall:
        for name, name_conf in firewall['name'].items():
            output_firewall_name_statistics(name, name_conf, ipv6=False)

    if 'ipv6_name' in firewall:
        for name, name_conf in firewall['ipv6_name'].items():
            output_firewall_name_statistics(name, name_conf, ipv6=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', help='Action', required=False)
    parser.add_argument('--name', help='Firewall name', required=False, action='store', nargs='?', default='')
    parser.add_argument('--rule', help='Firewall Rule ID', required=False)
    parser.add_argument('--ipv6', help='IPv6 toggle', action='store_true')

    args = parser.parse_args()

    if args.action == 'show':
        if not args.rule:
            show_firewall_name(args.name, args.ipv6)
        else:
            show_firewall_rule(args.name, args.rule, args.ipv6)
    elif args.action == 'show_all':
        show_firewall()
    elif args.action == 'show_group':
        show_firewall_group(args.name)
    elif args.action == 'show_statistics':
        show_statistics()
    elif args.action == 'show_summary':
        show_summary()
