#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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

from vyos.configquery import ConfigTreeQuery
from vyos.util import cmd


def get_firewall_bridge_name():
    """
    Return firewall policy bridge name
    Example:
    set firewall policy bridge forward ipv4 'FOO'
        returns 'FOO'
    """
    config = ConfigTreeQuery()
    name = ['firewall', 'policy', 'bridge', 'forward', 'ipv4']
    if config.exists(name):
        name = config.value(name)
        return name

def get_firewall_config(name):
    """
    Return dict firewall rules for required name
    """
    config = ConfigTreeQuery()
    base = ['firewall', 'name', name]
    if config.exists(base):
        firewall = config.get_config_dict(base, key_mangling=('-', '_'),
                                    get_first_key=True, no_tag_node_value_mangle=True)
        return firewall

def get_nftables_details(name):
    command = f'sudo nft list chain bridge filter {name}'
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

        rule['conditions'] = re.sub(r'(\b(counter packets \d+ bytes \d+|drop|return|log)\b|comment "[\w\-]+")', '', line).strip()
        out[rule_id] = rule
    return out

def output_firewall_name(name):
    print(f'\n---------------------------------\nBridge Firewall "{name}"\n')
    details = get_nftables_details(name)
    firewall = get_firewall_config(name)
    rows = []
    for rule, rule_conf in firewall['rule'].items():
        row = [rule, rule_conf['action'], rule_conf['protocol'] if 'protocol' in rule_conf else 'all']
        rule_details = details[rule]
        row.append(rule_details.get('packets', 0))
        row.append(rule_details.get('bytes', 0))
        row.append(rule_details['conditions'])
        rows.append(row)

    if 'default_action' in firewall:
        row = ['default']
        rule_details = details['default-action']
        row.append(firewall['default_action'])
        row.append('all')
        row.append(rule_details.get('packets', 0))
        row.append(rule_details.get('bytes', 0))
    else:
        row.append('0')
        row.append('0')
    row.append('src 0.0.0.0/0 dst 0.0.0.0/0')
    rows.append(row)

    if rows:
        header = ['Rule', 'Action', 'Protocol', 'Packets', 'Bytes', 'Conditions']
        print(tabulate.tabulate(rows, header) + '\n')

    return

parser = argparse.ArgumentParser()
parser.add_argument("--summary", action="store_true", help="Show all containers")

config = ConfigTreeQuery()
base = ['firewall', 'policy']

if not config.exists(base):
    print('Firewall policy not configured')
    exit(0)

if __name__ == '__main__':
    args = parser.parse_args()

    fw_name = get_firewall_bridge_name()
    if args.summary:
        output_firewall_name(fw_name)

    exit(0)
