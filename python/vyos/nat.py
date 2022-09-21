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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from vyos.template import is_ip_network
from vyos.util import dict_search_args

def parse_nat_rule(rule_conf, rule_id, nat_type, ipv6=False):
    output = []
    ip_prefix = 'ip6' if ipv6 else 'ip'
    log_prefix = ('DST' if nat_type == 'destination' else 'SRC') + f'-NAT-{rule_id}'
    log_suffix = ''

    if ipv6:
        log_prefix = log_prefix.replace("NAT-", "NAT66-")

    ignore_type_addr = False
    translation_str = ''

    if 'inbound_interface' in rule_conf:
        ifname = rule_conf['inbound_interface']
        if ifname != 'any':
            output.append(f'iifname "{ifname}"')

    if 'outbound_interface' in rule_conf:
        ifname = rule_conf['outbound_interface']
        if ifname != 'any':
            output.append(f'oifname "{ifname}"')

    if 'protocol' in rule_conf and rule_conf['protocol'] != 'all':
        protocol = rule_conf['protocol']
        if protocol == 'tcp_udp':
            protocol = '{ tcp, udp }'
        output.append(f'meta l4proto {protocol}')

    if 'exclude' in rule_conf:
        translation_str = 'return'
        log_suffix = '-EXCL'
    elif 'translation' in rule_conf:
        translation_prefix = nat_type[:1]
        translation_output = [f'{translation_prefix}nat']
        addr = dict_search_args(rule_conf, 'translation', 'address')
        port = dict_search_args(rule_conf, 'translation', 'port')

        if addr and is_ip_network(addr):
            if not ipv6:
                map_addr =  dict_search_args(rule_conf, nat_type, 'address')
                translation_output.append(f'{ip_prefix} prefix to {ip_prefix} {translation_prefix}addr map {{ {map_addr} : {addr} }}')
                ignore_type_addr = True
            else:
                translation_output.append(f'prefix to {addr}')
        elif addr == 'masquerade':
            if port:
                addr = f'{addr} to '
            translation_output = [addr]
            log_suffix = '-MASQ'
        else:
            translation_output.append('to')
            if addr:
                translation_output.append(addr)

        options = []
        addr_mapping = dict_search_args(rule_conf, 'translation', 'options', 'address_mapping')
        port_mapping = dict_search_args(rule_conf, 'translation', 'options', 'port_mapping')
        if addr_mapping == 'persistent':
            options.append('persistent')
        if port_mapping and port_mapping != 'none':
            options.append(port_mapping)

        translation_str = " ".join(translation_output) + (f':{port}' if port else '')

        if options:
            translation_str += f' {",".join(options)}'

    for target in ['source', 'destination']:
        prefix = target[:1]
        addr = dict_search_args(rule_conf, target, 'address')
        if addr and not (ignore_type_addr and target == nat_type):
            operator = ''
            if addr[:1] == '!':
                operator = '!='
                addr = addr[1:]
            output.append(f'{ip_prefix} {prefix}addr {operator} {addr}')

        addr_prefix = dict_search_args(rule_conf, target, 'prefix')
        if addr_prefix and ipv6:
            operator = ''
            if addr_prefix[:1] == '!':
                operator = '!='
                addr_prefix = addr[1:]
            output.append(f'ip6 {prefix}addr {operator} {addr_prefix}')

        port = dict_search_args(rule_conf, target, 'port')
        if port:
            protocol = rule_conf['protocol']
            if protocol == 'tcp_udp':
                protocol = 'th'
            operator = ''
            if port[:1] == '!':
                operator = '!='
                port = port[1:]
            output.append(f'{protocol} {prefix}port {operator} {{ {port} }}')

    output.append('counter')

    if 'log' in rule_conf:
        output.append(f'log prefix "[{log_prefix}{log_suffix}]"')

    if translation_str:
        output.append(translation_str)

    output.append(f'comment "{log_prefix}"')

    return " ".join(output)

def parse_nat_static_rule(rule_conf, rule_id, nat_type):
    output = []
    log_prefix = ('STATIC-DST' if nat_type == 'destination' else 'STATIC-SRC') + f'-NAT-{rule_id}'
    log_suffix = ''

    ignore_type_addr = False
    translation_str = ''

    if 'inbound_interface' in rule_conf:
        ifname = rule_conf['inbound_interface']
        ifprefix = 'i' if nat_type == 'destination' else 'o'
        if ifname != 'any':
            output.append(f'{ifprefix}ifname "{ifname}"')

    if 'exclude' in rule_conf:
        translation_str = 'return'
        log_suffix = '-EXCL'
    elif 'translation' in rule_conf:
        translation_prefix = nat_type[:1]
        translation_output = [f'{translation_prefix}nat']
        addr = dict_search_args(rule_conf, 'translation', 'address')
        map_addr =  dict_search_args(rule_conf, 'destination', 'address')

        if nat_type == 'source':
            addr, map_addr = map_addr, addr # Swap

        if addr and is_ip_network(addr):
            translation_output.append(f'ip prefix to ip {translation_prefix}addr map {{ {map_addr} : {addr} }}')
            ignore_type_addr = True
        elif addr:
            translation_output.append(f'to {addr}')

        options = []
        addr_mapping = dict_search_args(rule_conf, 'translation', 'options', 'address_mapping')
        port_mapping = dict_search_args(rule_conf, 'translation', 'options', 'port_mapping')
        if addr_mapping == 'persistent':
            options.append('persistent')
        if port_mapping and port_mapping != 'none':
            options.append(port_mapping)

        if options:
            translation_output.append(",".join(options))

        translation_str = " ".join(translation_output)

    prefix = nat_type[:1]
    addr = dict_search_args(rule_conf, 'translation' if nat_type == 'source' else nat_type, 'address')
    if addr and not ignore_type_addr:
        output.append(f'ip {prefix}addr {addr}')

    output.append('counter')

    if translation_str:
        output.append(translation_str)

    if 'log' in rule_conf:
        output.append(f'log prefix "[{log_prefix}{log_suffix}]"')

    output.append(f'comment "{log_prefix}"')

    return " ".join(output)
