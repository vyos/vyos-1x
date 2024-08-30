#!/usr/bin/env python3
#
# Copyright (C) 2022-2024 VyOS maintainers and contributors
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

import json
import time

from vyos.configdict import dict_merge
from vyos.configquery import ConfigTreeQuery
from vyos.firewall import fqdn_config_parse
from vyos.firewall import fqdn_resolve
from vyos.utils.commit import commit_in_progress
from vyos.utils.dict import dict_search_args
from vyos.utils.process import cmd
from vyos.utils.process import run
from vyos.xml_ref import get_defaults

base = ['firewall']
timeout = 300
cache = False
base_firewall = ['firewall']
base_nat = ['nat']

domain_state = {}

ipv4_tables = {
    'ip vyos_mangle',
    'ip vyos_filter',
    'ip vyos_nat',
    'ip raw'
}

ipv6_tables = {
    'ip6 vyos_mangle',
    'ip6 vyos_filter',
    'ip6 raw'
}

def get_config(conf, node):
    node_config = conf.get_config_dict(node, key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

    default_values = get_defaults(node, get_first_key=True)

    node_config = dict_merge(default_values, node_config)

    global timeout, cache

    if 'resolver_interval' in node_config:
        timeout = int(node_config['resolver_interval'])

    if 'resolver_cache' in node_config:
        cache = True

    fqdn_config_parse(node_config, node[0])

    return node_config

def resolve(domains, ipv6=False):
    global domain_state

    ip_list = set()

    for domain in domains:
        resolved = fqdn_resolve(domain, ipv6=ipv6)

        if resolved and cache:
            domain_state[domain] = resolved
        elif not resolved:
            if domain not in domain_state:
                continue
            resolved = domain_state[domain]

        ip_list = ip_list | resolved
    return ip_list

def nft_output(table, set_name, ip_list):
    output = [f'flush set {table} {set_name}']
    if ip_list:
        ip_str = ','.join(ip_list)
        output.append(f'add element {table} {set_name} {{ {ip_str} }}')
    return output

def nft_valid_sets():
    try:
        valid_sets = []
        sets_json = cmd('nft --json list sets')
        sets_obj = json.loads(sets_json)

        for obj in sets_obj['nftables']:
            if 'set' in obj:
                family = obj['set']['family']
                table = obj['set']['table']
                name = obj['set']['name']
                valid_sets.append((f'{family} {table}', name))

        return valid_sets
    except:
        return []

def update_fqdn(config, node):
    conf_lines = []
    count = 0
    valid_sets = nft_valid_sets()

    if node == 'firewall':
        domain_groups = dict_search_args(config, 'group', 'domain_group')
        if domain_groups:
            for set_name, domain_config in domain_groups.items():
                if 'address' not in domain_config:
                    continue
                nft_set_name = f'D_{set_name}'
                domains = domain_config['address']

                ip_list = resolve(domains, ipv6=False)
                for table in ipv4_tables:
                    if (table, nft_set_name) in valid_sets:
                        conf_lines += nft_output(table, nft_set_name, ip_list)
                ip6_list = resolve(domains, ipv6=True)
                for table in ipv6_tables:
                    if (table, nft_set_name) in valid_sets:
                        conf_lines += nft_output(table, nft_set_name, ip6_list)
                count += 1

        for set_name, domain in config['ip_fqdn'].items():
            table = 'ip vyos_filter'
            nft_set_name = f'FQDN_{set_name}'
            ip_list = resolve([domain], ipv6=False)
            if (table, nft_set_name) in valid_sets:
                conf_lines += nft_output(table, nft_set_name, ip_list)
            count += 1

        for set_name, domain in config['ip6_fqdn'].items():
            table = 'ip6 vyos_filter'
            nft_set_name = f'FQDN_{set_name}'
            ip_list = resolve([domain], ipv6=True)
            if (table, nft_set_name) in valid_sets:
                conf_lines += nft_output(table, nft_set_name, ip_list)
            count += 1

    else:
        # It's NAT
        for set_name, domain in config['ip_fqdn'].items():
            table = 'ip vyos_nat'
            nft_set_name = f'FQDN_nat_{set_name}'
            ip_list = resolve([domain], ipv6=False)
            if (table, nft_set_name) in valid_sets:
                conf_lines += nft_output(table, nft_set_name, ip_list)
            count += 1

    nft_conf_str = "\n".join(conf_lines) + "\n"
    code = run(f'nft --file -', input=nft_conf_str)

    print(f'Updated {count} sets in {node} - result: {code}')

if __name__ == '__main__':
    print(f'VyOS domain resolver')

    count = 1
    while commit_in_progress():
        if ( count % 60 == 0 ):
            print(f'Commit still in progress after {count}s - waiting')
        count += 1
        time.sleep(1)

    conf = ConfigTreeQuery()
    firewall = get_config(conf, base_firewall)
    nat = get_config(conf, base_nat)

    print(f'interval: {timeout}s - cache: {cache}')

    while True:
        update_fqdn(firewall, 'firewall')
        update_fqdn(nat, 'nat')
        time.sleep(timeout)
