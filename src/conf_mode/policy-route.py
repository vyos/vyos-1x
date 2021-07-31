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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os

from json import loads
from sys import exit

from vyos.config import Config
from vyos.template import render
from vyos.util import cmd
from vyos.util import dict_search_args
from vyos.util import run
from vyos import ConfigError
from vyos import airbag
airbag.enable()

mark_offset = 0x7FFFFFFF
nftables_conf = '/run/nftables_policy.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['policy']

    if not conf.exists(base + ['route']) and not conf.exists(base + ['ipv6-route']):
        return None

    policy = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

    return policy

def verify(policy):
    # bail out early - looks like removal from running config
    if not policy:
        return None

    for route in ['route', 'ipv6_route']:
        if route in policy:
            for name, pol_conf in policy[route].items():
                if 'rule' in pol_conf:
                    for rule_id, rule_conf in pol_conf.items():
                        icmp = 'icmp' if route == 'route' else 'icmpv6'
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
                                if not tcp_flags or 'SYN' not in tcp_flags.split(","):
                                    raise ConfigError(f'{name} rule {rule_id}: TCP SYN flag must be set to modify TCP-MSS')
                        if 'tcp' in rule_conf:
                            if 'flags' in rule_conf['tcp']:
                                if 'protocol' not in rule_conf or rule_conf['protocol'] != 'tcp':
                                    raise ConfigError(f'{name} rule {rule_id}: TCP flags can only be set if protocol is set to TCP')


    return None

def generate(policy):
    if not policy:
        if os.path.exists(nftables_conf):
            os.unlink(nftables_conf)
        return None

    if not os.path.exists(nftables_conf):
        policy['first_install'] = True

    render(nftables_conf, 'firewall/nftables-policy.tmpl', policy)
    return None

def apply_table_marks(policy):
    for route in ['route', 'ipv6_route']:
        if route in policy:
            for name, pol_conf in policy[route].items():
                if 'rule' in pol_conf:
                    for rule_id, rule_conf in pol_conf['rule'].items():
                        set_table = dict_search_args(rule_conf, 'set', 'table')
                        if set_table:
                            if set_table == 'main':
                                set_table = '254'
                            table_mark = mark_offset - int(set_table)
                            cmd(f'ip rule add fwmark {table_mark} table {set_table}')

def cleanup_table_marks():
    json_rules = cmd('ip -j -N rule list')
    rules = loads(json_rules)
    for rule in rules:
        if 'fwmark' not in rule or 'table' not in rule:
            continue
        fwmark = rule['fwmark']
        table = int(rule['table'])
        if fwmark[:2] == '0x':
            fwmark = int(fwmark, 16)
        if (int(fwmark) == (mark_offset - table)):
            cmd(f'ip rule del fwmark {fwmark} table {table}')

def apply(policy):
    if not policy or 'first_install' not in policy:
        run(f'nft flush table ip mangle')
        run(f'nft flush table ip6 mangle')

    if not policy:
        cleanup_table_marks()
        return None

    install_result = run(f'nft -f {nftables_conf}')
    if install_result == 1:
        raise ConfigError('Failed to apply policy based routing')

    if 'first_install' not in policy:
        cleanup_table_marks()

    apply_table_marks(policy)

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
