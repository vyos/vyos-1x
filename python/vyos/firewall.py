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

import re

from vyos.util import cmd
from vyos.util import dict_search_args

def find_nftables_rule(table, chain, rule_matches=[]):
    # Find rule in table/chain that matches all criteria and return the handle
    results = cmd(f'sudo nft -a list chain {table} {chain}').split("\n")
    for line in results:
        if all(rule_match in line for rule_match in rule_matches):
            handle_search = re.search('handle (\d+)', line)
            if handle_search:
                return handle_search[1]
    return None

def remove_nftables_rule(table, chain, handle):
    cmd(f'sudo nft delete rule {table} {chain} handle {handle}')

# Functions below used by template generation

def nft_action(vyos_action):
    if vyos_action == 'accept':
        return 'return'
    return vyos_action

def parse_rule(rule_conf, fw_name, rule_id, ip_name):
    output = []
    def_suffix = '6' if ip_name == 'ip6' else ''

    if 'state' in rule_conf and rule_conf['state']:
        states = ",".join([s for s, v in rule_conf['state'].items() if v == 'enable'])

        if states:
            output.append(f'ct state {{{states}}}')

    if 'protocol' in rule_conf and rule_conf['protocol'] != 'all':
        proto = rule_conf['protocol']
        operator = ''
        if proto[0] == '!':
            operator = '!='
            proto = proto[1:]
        if proto == 'tcp_udp':
            proto = '{tcp, udp}'
        output.append(f'meta l4proto {operator} {proto}')

    for side in ['destination', 'source']:
        if side in rule_conf:
            prefix = side[0]
            side_conf = rule_conf[side]

            if 'address' in side_conf:
                suffix = side_conf['address']
                if suffix[0] == '!':
                    suffix = f'!= {suffix[1:]}'
                output.append(f'{ip_name} {prefix}addr {suffix}')

            if 'mac_address' in side_conf:
                suffix = side_conf["mac_address"]
                if suffix[0] == '!':
                    suffix = f'!= {suffix[1:]}'
                output.append(f'ether {prefix}addr {suffix}')

            if 'port' in side_conf:
                proto = rule_conf['protocol']
                port = side_conf['port'].split(',')

                ports = []
                negated_ports = []

                for p in port:
                    if p[0] == '!':
                        negated_ports.append(p[1:])
                    else:
                        ports.append(p)

                if proto == 'tcp_udp':
                    proto = 'th'

                if ports:
                    ports_str = ','.join(ports)
                    output.append(f'{proto} {prefix}port {{{ports_str}}}')

                if negated_ports:
                    negated_ports_str = ','.join(negated_ports)
                    output.append(f'{proto} {prefix}port != {{{negated_ports_str}}}')

            if 'group' in side_conf:
                group = side_conf['group']
                if 'address_group' in group:
                    group_name = group['address_group']
                    output.append(f'{ip_name} {prefix}addr $A{def_suffix}_{group_name}')
                elif 'network_group' in group:
                    group_name = group['network_group']
                    output.append(f'{ip_name} {prefix}addr $N{def_suffix}_{group_name}')
                if 'port_group' in group:
                    proto = rule_conf['protocol']
                    group_name = group['port_group']

                    if proto == 'tcp_udp':
                        proto = 'th'

                    output.append(f'{proto} {prefix}port $P_{group_name}')

    if 'log' in rule_conf and rule_conf['log'] == 'enable':
        output.append('log')

    if 'hop_limit' in rule_conf:
        operators = {'eq': '==', 'gt': '>', 'lt': '<'}
        for op, operator in operators.items():
            if op in rule_conf['hop_limit']:
                value = rule_conf['hop_limit'][op]
                output.append(f'ip6 hoplimit {operator} {value}')

    for icmp in ['icmp', 'icmpv6']:
        if icmp in rule_conf:
            if 'type_name' in rule_conf[icmp]:
                output.append(icmp + ' type ' + rule_conf[icmp]['type_name'])
            else:
                if 'code' in rule_conf[icmp]:
                    output.append(icmp + ' code ' + rule_conf[icmp]['code'])
                if 'type' in rule_conf[icmp]:
                    output.append(icmp + ' type ' + rule_conf[icmp]['type'])

    if 'ipsec' in rule_conf:
        if 'match_ipsec' in rule_conf['ipsec']:
            output.append('meta ipsec == 1')
        if 'match_non_ipsec' in rule_conf['ipsec']:
            output.append('meta ipsec == 0')

    if 'fragment' in rule_conf:
        # Checking for fragmentation after priority -400 is not possible,
        # so we use a priority -450 hook to set a mark
        if 'match_frag' in rule_conf['fragment']:
            output.append('meta mark 0xffff1')
        if 'match_non_frag' in rule_conf['fragment']:
            output.append('meta mark != 0xffff1')

    if 'limit' in rule_conf:
        if 'rate' in rule_conf['limit']:
            output.append(f'limit rate {rule_conf["limit"]["rate"]}/second')
            if 'burst' in rule_conf['limit']:
                output.append(f'burst {rule_conf["limit"]["burst"]} packets')

    if 'recent' in rule_conf:
        count = rule_conf['recent']['count']
        time = rule_conf['recent']['time']
        # output.append(f'meter {fw_name}_{rule_id} {{ ip saddr and 255.255.255.255 limit rate over {count}/{time} burst {count} packets }}')
        # Waiting on input from nftables developers due to
        # bug with above line and atomic chain flushing.

    if 'time' in rule_conf:
        output.append(parse_time(rule_conf['time']))

    tcp_flags = dict_search_args(rule_conf, 'tcp', 'flags')
    if tcp_flags:
        output.append(parse_tcp_flags(tcp_flags))


    output.append('counter')

    if 'set' in rule_conf:
        output.append(parse_policy_set(rule_conf['set'], def_suffix))

    if 'action' in rule_conf:
        output.append(nft_action(rule_conf['action']))
    else:
        output.append('return')

    output.append(f'comment "{fw_name}-{rule_id}"')
    return " ".join(output)

def parse_tcp_flags(flags):
    all_flags = []
    include = []
    for flag in flags.split(","):
        if flag[0] == '!':
            flag = flag[1:]
        else:
            include.append(flag)
        all_flags.append(flag)
    return f'tcp flags & ({"|".join(all_flags)}) == {"|".join(include)}'

def parse_time(time):
    out = []
    if 'startdate' in time:
        start = time['startdate']
        if 'T' not in start and 'starttime' in time:
            start += f' {time["starttime"]}'
        out.append(f'time >= "{start}"')
    if 'starttime' in time and 'startdate' not in time:
        out.append(f'hour >= "{time["starttime"]}"')
    if 'stopdate' in time:
        stop = time['stopdate']
        if 'T' not in stop and 'stoptime' in time:
            stop += f' {time["stoptime"]}'
        out.append(f'time < "{stop}"')
    if 'stoptime' in time and 'stopdate' not in time:
        out.append(f'hour < "{time["stoptime"]}"')
    if 'weekdays' in time:
        days = time['weekdays'].split(",")
        out_days = [f'"{day}"' for day in days if day[0] != '!']
        out.append(f'day {{{",".join(out_days)}}}')
    return " ".join(out)

def parse_policy_set(set_conf, def_suffix):
    out = []
    if 'dscp' in set_conf:
        dscp = set_conf['dscp']
        out.append(f'ip{def_suffix} dscp set {dscp}')
    if 'mark' in set_conf:
        mark = set_conf['mark']
        out.append(f'meta mark set {mark}')
    if 'table' in set_conf:
        table = set_conf['table']
        if table == 'main':
            table = '254'
        mark = 0x7FFFFFFF - int(table)
        out.append(f'meta mark set {mark}')
    if 'tcp_mss' in set_conf:
        mss = set_conf['tcp_mss']
        out.append(f'tcp option maxseg size set {mss}')
    return " ".join(out)
