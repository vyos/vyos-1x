#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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
import re
import tabulate

from vyos.config import Config
from vyos.utils.process import cmd

def get_config_policy(conf, name=None, ipv6=False):
    config_path = ['policy']
    if name:
        config_path += ['route6' if ipv6 else 'route', name]

    policy = conf.get_config_dict(config_path, key_mangling=('-', '_'),
                                get_first_key=True, no_tag_node_value_mangle=True)

    return policy

def get_nftables_details(name, ipv6=False):
    suffix = '6' if ipv6 else ''
    command = f'sudo nft list chain ip{suffix} mangle VYOS_PBR{suffix}_{name}'
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

def output_policy_route(name, route_conf, ipv6=False, single_rule_id=None):
    ip_str = 'IPv6' if ipv6 else 'IPv4'
    print(f'\n---------------------------------\n{ip_str} Policy Route "{name}"\n')

    if route_conf.get('interface'):
        print('Active on: {0}\n'.format(" ".join(route_conf['interface'])))
    else:
        print('Inactive - Not applied to any interfaces\n')

    details = get_nftables_details(name, ipv6)
    rows = []

    if 'rule' in route_conf:
        for rule_id, rule_conf in route_conf['rule'].items():
            if single_rule_id and rule_id != single_rule_id:
                continue

            if 'disable' in rule_conf:
                continue

            action = rule_conf['action'] if 'action' in rule_conf else 'set'
            protocol = rule_conf['protocol'] if 'protocol' in rule_conf else 'all'

            row = [rule_id, action, protocol]
            if rule_id in details:
                rule_details = details[rule_id]
                row.append(rule_details.get('packets', 0))
                row.append(rule_details.get('bytes', 0))
                row.append(rule_details['conditions'])
            rows.append(row)

    if 'default_action' in route_conf and not single_rule_id:
        row = ['default', route_conf['default_action'], 'all']
        if 'default-action' in details:
            rule_details = details['default-action']
            row.append(rule_details.get('packets', 0))
            row.append(rule_details.get('bytes', 0))
        rows.append(row)

    if rows:
        header = ['Rule', 'Action', 'Protocol', 'Packets', 'Bytes', 'Conditions']
        print(tabulate.tabulate(rows, header) + '\n')

def show_policy(ipv6=False):
    print('Ruleset Information')

    conf = Config()
    policy = get_config_policy(conf)

    if not policy:
        return

    if not ipv6 and 'route' in policy:
        for route, route_conf in policy['route'].items():
            output_policy_route(route, route_conf, ipv6=False)

    if ipv6 and 'route6' in policy:
        for route, route_conf in policy['route6'].items():
            output_policy_route(route, route_conf, ipv6=True)

def show_policy_name(name, ipv6=False):
    print('Ruleset Information')

    conf = Config()
    policy = get_config_policy(conf, name, ipv6)
    if policy:
        output_policy_route(name, policy, ipv6)

def show_policy_rule(name, rule_id, ipv6=False):
    print('Rule Information')

    conf = Config()
    policy = get_config_policy(conf, name, ipv6)
    if policy:
        output_policy_route(name, policy, ipv6, rule_id)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', help='Action', required=False)
    parser.add_argument('--name', help='Policy name', required=False, action='store', nargs='?', default='')
    parser.add_argument('--rule', help='Policy Rule ID', required=False)
    parser.add_argument('--ipv6', help='IPv6 toggle', action='store_true')

    args = parser.parse_args()

    if args.action == 'show':
        if not args.rule:
            show_policy_name(args.name, args.ipv6)
        else:
            show_policy_rule(args.name, args.rule, args.ipv6)
    elif args.action == 'show_all':
        show_policy(args.ipv6)
