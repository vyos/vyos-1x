# Copyright (C) 2021-2024 VyOS maintainers and contributors
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

import csv
import gzip
import os
import re

from pathlib import Path
from socket import AF_INET
from socket import AF_INET6
from socket import getaddrinfo
from time import strftime

from vyos.remote import download
from vyos.template import is_ipv4
from vyos.template import render
from vyos.utils.dict import dict_search_args
from vyos.utils.dict import dict_search_recursive
from vyos.utils.process import cmd
from vyos.utils.process import run
from vyos.utils.network import get_vrf_tableid
from vyos.defaults import rt_global_table
from vyos.defaults import rt_global_vrf

# Conntrack
def conntrack_required(conf):
    required_nodes = ['nat', 'nat66', 'load-balancing wan']

    for path in required_nodes:
        if conf.exists(path):
            return True

    firewall = conf.get_config_dict(['firewall'], key_mangling=('-', '_'),
                                    no_tag_node_value_mangle=True, get_first_key=True)

    for rules, path in dict_search_recursive(firewall, 'rule'):
        if any(('state' in rule_conf or 'connection_status' in rule_conf or 'offload_target' in rule_conf) for rule_conf in rules.values()):
            return True

    return False

# Domain Resolver

def fqdn_config_parse(config, node):
    config['ip_fqdn'] = {}
    config['ip6_fqdn'] = {}

    for domain, path in dict_search_recursive(config, 'fqdn'):
        if node != 'nat':
            hook_name = path[1]
            priority = path[2]

            rule = path[4]
            suffix = path[5][0]
            set_name = f'{hook_name}_{priority}_{rule}_{suffix}'

            if (path[0] == 'ipv4') and (path[1] == 'forward' or path[1] == 'input' or path[1] == 'output' or path[1] == 'name'):
                config['ip_fqdn'][set_name] = domain
            elif (path[0] == 'ipv6') and (path[1] == 'forward' or path[1] == 'input' or path[1] == 'output' or path[1] == 'name'):
                if path[1] == 'name':
                    set_name = f'name6_{priority}_{rule}_{suffix}'
                config['ip6_fqdn'][set_name] = domain
        else:
            # Parse FQDN for NAT
            nat_direction = path[0]
            nat_rule = path[2]
            suffix = path[3][0]
            set_name = f'{nat_direction}_{nat_rule}_{suffix}'
            config['ip_fqdn'][set_name] = domain

def fqdn_resolve(fqdn, ipv6=False):
    try:
        res = getaddrinfo(fqdn, None, AF_INET6 if ipv6 else AF_INET)
        return set(item[4][0] for item in res)
    except:
        return None

def find_nftables_rule(table, chain, rule_matches=[]):
    # Find rule in table/chain that matches all criteria and return the handle
    results = cmd(f'sudo nft --handle list chain {table} {chain}').split("\n")
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

def parse_rule(rule_conf, hook, fw_name, rule_id, ip_name):
    output = []

    if ip_name == 'ip6':
        def_suffix = '6'
        family = 'ipv6'
    else:
        def_suffix = ''
        family = 'bri' if ip_name == 'bri' else 'ipv4'

    if 'state' in rule_conf and rule_conf['state']:
        states = ",".join([s for s in rule_conf['state']])

        if states:
            output.append(f'ct state {{{states}}}')

    if 'conntrack_helper' in rule_conf:
        helper_map = {'h323': ['RAS', 'Q.931'], 'nfs': ['rpc'], 'sqlnet': ['tns']}
        helper_out = []

        for helper in rule_conf['conntrack_helper']:
            if helper in helper_map:
                helper_out.extend(helper_map[helper])
            else:
                helper_out.append(helper)

        if helper_out:
            helper_str = ','.join(f'"{s}"' for s in helper_out)
            output.append(f'ct helper {{{helper_str}}}')

    if 'connection_status' in rule_conf and rule_conf['connection_status']:
        status = rule_conf['connection_status']
        if status['nat'] == 'destination':
            nat_status = 'dnat'
            output.append(f'ct status {nat_status}')
        if status['nat'] == 'source':
            nat_status = 'snat'
            output.append(f'ct status {nat_status}')

    if 'protocol' in rule_conf and rule_conf['protocol'] != 'all':
        proto = rule_conf['protocol']
        operator = ''
        if proto[0] == '!':
            operator = '!='
            proto = proto[1:]
        if proto == 'tcp_udp':
            proto = '{tcp, udp}'
        output.append(f'meta l4proto {operator} {proto}')

    if 'ethernet_type' in rule_conf:
        ether_type_mapping = {
            '802.1q': '8021q',
            '802.1ad': '8021ad',
            'ipv6': 'ip6',
            'ipv4': 'ip',
            'arp': 'arp'
        }
        ether_type = rule_conf['ethernet_type']
        operator = '!=' if ether_type.startswith('!') else ''
        ether_type = ether_type.lstrip('!')
        ether_type = ether_type_mapping.get(ether_type, ether_type)
        output.append(f'ether type {operator} {ether_type}')

    for side in ['destination', 'source']:
        if side in rule_conf:
            prefix = side[0]
            side_conf = rule_conf[side]
            address_mask = side_conf.get('address_mask', None)

            if 'address' in side_conf:
                suffix = side_conf['address']
                operator = ''
                exclude = suffix[0] == '!'
                if exclude:
                    operator = '!= '
                    suffix = suffix[1:]
                if address_mask:
                    operator = '!=' if exclude else '=='
                    operator = f'& {address_mask} {operator} '

                if suffix.find('-') != -1:
                    # Range
                    start, end = suffix.split('-')
                    if is_ipv4(start):
                        output.append(f'ip {prefix}addr {operator}{suffix}')
                    else:
                        output.append(f'ip6 {prefix}addr {operator}{suffix}')
                else:
                    if is_ipv4(suffix):
                        output.append(f'ip {prefix}addr {operator}{suffix}')
                    else:
                        output.append(f'ip6 {prefix}addr {operator}{suffix}')

            if 'fqdn' in side_conf:
                fqdn = side_conf['fqdn']
                hook_name = ''
                operator = ''
                if fqdn[0] == '!':
                    operator = '!='
                if hook == 'FWD':
                    hook_name = 'forward'
                if hook == 'INP':
                    hook_name = 'input'
                if hook == 'OUT':
                    hook_name = 'output'
                if hook == 'PRE':
                    hook_name = 'prerouting'
                if hook == 'NAM':
                    hook_name = f'name{def_suffix}'
                output.append(f'{ip_name} {prefix}addr {operator} @FQDN_{hook_name}_{fw_name}_{rule_id}_{prefix}')

            if dict_search_args(side_conf, 'geoip', 'country_code'):
                operator = ''
                hook_name = ''
                if dict_search_args(side_conf, 'geoip', 'inverse_match') != None:
                    operator = '!='
                if hook == 'FWD':
                    hook_name = 'forward'
                if hook == 'INP':
                    hook_name = 'input'
                if hook == 'OUT':
                    hook_name = 'output'
                if hook == 'PRE':
                    hook_name = 'prerouting'
                if hook == 'NAM':
                    hook_name = f'name'
                output.append(f'{ip_name} {prefix}addr {operator} @GEOIP_CC{def_suffix}_{hook_name}_{fw_name}_{rule_id}')

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
                for ipvx_address_group in ['address_group', 'ipv4_address_group', 'ipv6_address_group']:
                    if ipvx_address_group in group:
                        group_name = group[ipvx_address_group]
                        operator = ''
                        exclude = group_name[0] == "!"
                        if exclude:
                            operator = '!='
                            group_name = group_name[1:]
                        if address_mask:
                            operator = '!=' if exclude else '=='
                            operator = f'& {address_mask} {operator}'
                        # for bridge, change ip_name
                        if ip_name == 'bri':
                            ip_name = 'ip' if ipvx_address_group == 'ipv4_address_group' else 'ip6'
                            def_suffix = '6' if ipvx_address_group == 'ipv6_address_group' else ''
                        output.append(f'{ip_name} {prefix}addr {operator} @A{def_suffix}_{group_name}')
                for ipvx_network_group in ['network_group', 'ipv4_network_group', 'ipv6_network_group']:
                    if ipvx_network_group in group:
                        group_name = group[ipvx_network_group]
                        operator = ''
                        if group_name[0] == "!":
                            operator = '!='
                            group_name = group_name[1:]
                        # for bridge, change ip_name
                        if ip_name == 'bri':
                            ip_name = 'ip' if ipvx_network_group == 'ipv4_network_group' else 'ip6'
                            def_suffix = '6' if ipvx_network_group == 'ipv6_network_group' else ''
                        output.append(f'{ip_name} {prefix}addr {operator} @N{def_suffix}_{group_name}')
                if 'dynamic_address_group' in group:
                    group_name = group['dynamic_address_group']
                    operator = ''
                    if group_name[0] == "!":
                        operator = '!='
                        group_name = group_name[1:]
                    output.append(f'{ip_name} {prefix}addr {operator} @DA{def_suffix}_{group_name}')
                # Generate firewall group domain-group
                elif 'domain_group' in group:
                    group_name = group['domain_group']
                    operator = ''
                    if group_name[0] == '!':
                        operator = '!='
                        group_name = group_name[1:]
                    output.append(f'{ip_name} {prefix}addr {operator} @D_{group_name}')
                if 'mac_group' in group:
                    group_name = group['mac_group']
                    operator = ''
                    if group_name[0] == '!':
                        operator = '!='
                        group_name = group_name[1:]
                    output.append(f'ether {prefix}addr {operator} @M_{group_name}')
                if 'port_group' in group:
                    proto = rule_conf['protocol']
                    group_name = group['port_group']

                    if proto == 'tcp_udp':
                        proto = 'th'

                    operator = ''
                    if group_name[0] == '!':
                        operator = '!='
                        group_name = group_name[1:]

                    output.append(f'{proto} {prefix}port {operator} @P_{group_name}')

    if dict_search_args(rule_conf, 'action') == 'synproxy':
        output.append('ct state invalid,untracked')

    if 'hop_limit' in rule_conf:
        operators = {'eq': '==', 'gt': '>', 'lt': '<'}
        for op, operator in operators.items():
            if op in rule_conf['hop_limit']:
                value = rule_conf['hop_limit'][op]
                output.append(f'ip6 hoplimit {operator} {value}')

    if 'inbound_interface' in rule_conf:
        operator = ''
        if 'name' in rule_conf['inbound_interface']:
            iiface = rule_conf['inbound_interface']['name']
            if iiface[0] == '!':
                operator = '!='
                iiface = iiface[1:]
            output.append(f'iifname {operator} {{{iiface}}}')
        elif 'group' in rule_conf['inbound_interface']:
            iiface = rule_conf['inbound_interface']['group']
            if iiface[0] == '!':
                operator = '!='
                iiface = iiface[1:]
            output.append(f'iifname {operator} @I_{iiface}')

    if 'outbound_interface' in rule_conf:
        operator = ''
        if 'name' in rule_conf['outbound_interface']:
            oiface = rule_conf['outbound_interface']['name']
            if oiface[0] == '!':
                operator = '!='
                oiface = oiface[1:]
            output.append(f'oifname {operator} {{{oiface}}}')
        elif 'group' in rule_conf['outbound_interface']:
            oiface = rule_conf['outbound_interface']['group']
            if oiface[0] == '!':
                operator = '!='
                oiface = oiface[1:]
            output.append(f'oifname {operator} @I_{oiface}')

    if 'ttl' in rule_conf:
        operators = {'eq': '==', 'gt': '>', 'lt': '<'}
        for op, operator in operators.items():
            if op in rule_conf['ttl']:
                value = rule_conf['ttl'][op]
                output.append(f'ip ttl {operator} {value}')

    for icmp in ['icmp', 'icmpv6']:
        if icmp in rule_conf:
            if 'type_name' in rule_conf[icmp]:
                output.append(icmp + ' type ' + rule_conf[icmp]['type_name'])
            else:
                if 'code' in rule_conf[icmp]:
                    output.append(icmp + ' code ' + rule_conf[icmp]['code'])
                if 'type' in rule_conf[icmp]:
                    output.append(icmp + ' type ' + rule_conf[icmp]['type'])


    if 'packet_length' in rule_conf:
        lengths_str = ','.join(rule_conf['packet_length'])
        output.append(f'ip{def_suffix} length {{{lengths_str}}}')

    if 'packet_length_exclude' in rule_conf:
        negated_lengths_str = ','.join(rule_conf['packet_length_exclude'])
        output.append(f'ip{def_suffix} length != {{{negated_lengths_str}}}')

    if 'packet_type' in rule_conf:
        output.append(f'pkttype ' + rule_conf['packet_type'])

    if 'dscp' in rule_conf:
        dscp_str = ','.join(rule_conf['dscp'])
        output.append(f'ip{def_suffix} dscp {{{dscp_str}}}')

    if 'dscp_exclude' in rule_conf:
        negated_dscp_str = ','.join(rule_conf['dscp_exclude'])
        output.append(f'ip{def_suffix} dscp != {{{negated_dscp_str}}}')

    if 'ipsec' in rule_conf:
        if 'match_ipsec_in' in rule_conf['ipsec']:
            output.append('meta ipsec == 1')
        if 'match_none_in' in rule_conf['ipsec']:
            output.append('meta ipsec == 0')
        if 'match_ipsec_out' in rule_conf['ipsec']:
            output.append('rt ipsec exists')
        if 'match_none_out' in rule_conf['ipsec']:
            output.append('rt ipsec missing')

    if 'fragment' in rule_conf:
        # Checking for fragmentation after priority -400 is not possible,
        # so we use a priority -450 hook to set a mark
        if 'match_frag' in rule_conf['fragment']:
            output.append('meta mark 0xffff1')
        if 'match_non_frag' in rule_conf['fragment']:
            output.append('meta mark != 0xffff1')

    if 'limit' in rule_conf:
        if 'rate' in rule_conf['limit']:
            output.append(f'limit rate {rule_conf["limit"]["rate"]}')
            if 'burst' in rule_conf['limit']:
                output.append(f'burst {rule_conf["limit"]["burst"]} packets')

    if 'recent' in rule_conf:
        count = rule_conf['recent']['count']
        time = rule_conf['recent']['time']
        output.append(f'add @RECENT{def_suffix}_{hook}_{fw_name}_{rule_id} {{ {ip_name} saddr limit rate over {count}/{time} burst {count} packets }}')

    if 'gre' in rule_conf:
        gre_key = dict_search_args(rule_conf, 'gre', 'key')

        gre_flags = dict_search_args(rule_conf, 'gre', 'flags')
        output.append(parse_gre_flags(gre_flags or {}, force_keyed=gre_key is not None))

        gre_proto_alias_map = {
            '802.1q': '8021q',
            '802.1ad': '8021ad',
            'gretap': '0x6558',
        }

        gre_proto = dict_search_args(rule_conf, 'gre', 'inner_proto')
        if gre_proto is not None:
            gre_proto = gre_proto_alias_map.get(gre_proto, gre_proto)
            output.append(f'gre protocol {gre_proto}')

        gre_ver = dict_search_args(rule_conf, 'gre', 'version')
        if gre_ver == 'gre':
            output.append('gre version 0')
        elif gre_ver == 'pptp':
            output.append('gre version 1')

        if gre_key:
            # The offset of the key within the packet shifts depending on the C-flag. 
            # nftables cannot handle complex enough expressions to match multiple 
            # offsets based on bitfields elsewhere.
            # We enforce a specific match for the checksum flag in validation, so the 
            # gre_flags dict will always have a 'checksum' key when gre_key is populated. 
            if not gre_flags['checksum']: 
                # No "unset" child node means C is set, we offset key lookup +32 bits
                output.append(f'@th,64,32 == {gre_key}')                
            else:
                output.append(f'@th,32,32 == {gre_key}')

    if 'time' in rule_conf:
        output.append(parse_time(rule_conf['time']))

    tcp_flags = dict_search_args(rule_conf, 'tcp', 'flags')
    if tcp_flags:
        output.append(parse_tcp_flags(tcp_flags))

    # TCP MSS
    tcp_mss = dict_search_args(rule_conf, 'tcp', 'mss')
    if tcp_mss:
        output.append(f'tcp option maxseg size {tcp_mss}')

    if 'connection_mark' in rule_conf:
        conn_mark_str = ','.join(rule_conf['connection_mark'])
        output.append(f'ct mark {{{conn_mark_str}}}')

    if 'mark' in rule_conf:
        mark = rule_conf['mark']
        operator = ''
        if mark[0] == '!':
            operator = '!='
            mark = mark[1:]
        output.append(f'meta mark {operator} {{{mark}}}')

    if 'vlan' in rule_conf:
        if 'id' in rule_conf['vlan']:
            output.append(f'vlan id {rule_conf["vlan"]["id"]}')
        if 'priority' in rule_conf['vlan']:
            output.append(f'vlan pcp {rule_conf["vlan"]["priority"]}')
        if 'ethernet_type' in rule_conf['vlan']:
            ether_type_mapping = {
                '802.1q': '8021q',
                '802.1ad': '8021ad',
                'ipv6': 'ip6',
                'ipv4': 'ip',
                'arp': 'arp'
            }
            ether_type = rule_conf['vlan']['ethernet_type']
            operator = '!=' if ether_type.startswith('!') else ''
            ether_type = ether_type.lstrip('!')
            ether_type = ether_type_mapping.get(ether_type, ether_type)
            output.append(f'vlan type {operator} {ether_type}')

    if 'log' in rule_conf:
        action = rule_conf['action'] if 'action' in rule_conf else 'accept'
        #output.append(f'log prefix "[{fw_name[:19]}-{rule_id}-{action[:1].upper()}]"')
        output.append(f'log prefix "[{family}-{hook}-{fw_name}-{rule_id}-{action[:1].upper()}]"')
                        ##{family}-{hook}-{fw_name}-{rule_id}
        if 'log_options' in rule_conf:

            if 'level' in rule_conf['log_options']:
                log_level = rule_conf['log_options']['level']
                output.append(f'log level {log_level}')

            if 'group' in rule_conf['log_options']:
                log_group = rule_conf['log_options']['group']
                output.append(f'log group {log_group}')

                if 'queue_threshold' in rule_conf['log_options']:
                    queue_threshold = rule_conf['log_options']['queue_threshold']
                    output.append(f'queue-threshold {queue_threshold}')

                if 'snapshot_length' in rule_conf['log_options']:
                    log_snaplen = rule_conf['log_options']['snapshot_length']
                    output.append(f'snaplen {log_snaplen}')

    output.append('counter')

    if 'add_address_to_group' in rule_conf:
        for side in ['destination_address', 'source_address']:
            if side in rule_conf['add_address_to_group']:
                prefix = side[0]
                side_conf = rule_conf['add_address_to_group'][side]
                dyn_group = side_conf['address_group']
                if 'timeout' in side_conf:
                    timeout_value = side_conf['timeout']
                    output.append(f'set update ip{def_suffix} {prefix}addr timeout {timeout_value} @DA{def_suffix}_{dyn_group}')
                else:
                    output.append(f'set update ip{def_suffix} saddr @DA{def_suffix}_{dyn_group}')

    set_table = False
    if 'set' in rule_conf:
        # Parse set command used in policy route:
        if 'connection_mark' in rule_conf['set']:
            conn_mark = rule_conf['set']['connection_mark']
            output.append(f'ct mark set {conn_mark}')
        if 'dscp' in rule_conf['set']:
            dscp = rule_conf['set']['dscp']
            output.append(f'ip{def_suffix} dscp set {dscp}')
        if 'mark' in rule_conf['set']:
            mark = rule_conf['set']['mark']
            output.append(f'meta mark set {mark}')
        if 'vrf' in rule_conf['set']:
            set_table = True
            vrf_name = rule_conf['set']['vrf']
            if vrf_name == 'default':
                table = rt_global_vrf
            else:
                # NOTE: VRF->table ID lookup depends on the VRF iface already existing.
                table = get_vrf_tableid(vrf_name)
        if 'table' in rule_conf['set']:
            set_table = True
            table = rule_conf['set']['table']
            if table == 'main':
                table = rt_global_table
        if set_table:
            mark = 0x7FFFFFFF - int(table)
            output.append(f'meta mark set {mark}')
        if 'tcp_mss' in rule_conf['set']:
            mss = rule_conf['set']['tcp_mss']
            output.append(f'tcp option maxseg size set {mss}')
        if 'ttl' in rule_conf['set']:
            ttl = rule_conf['set']['ttl']
            output.append(f'ip ttl set {ttl}')
        if 'hop_limit' in rule_conf['set']:
            hoplimit = rule_conf['set']['hop_limit']
            output.append(f'ip6 hoplimit set {hoplimit}')

    if 'action' in rule_conf:
        if rule_conf['action'] == 'offload':
            offload_target = rule_conf['offload_target']
            output.append(f'flow add @VYOS_FLOWTABLE_{offload_target}')
        else:
            output.append(f'{rule_conf["action"]}')

            if 'jump' in rule_conf['action']:
                target = rule_conf['jump_target']
                output.append(f'NAME{def_suffix}_{target}')

            if 'queue' in rule_conf['action']:
                if 'queue' in rule_conf:
                    target = rule_conf['queue']
                    output.append(f'num {target}')

                if 'queue_options' in rule_conf:
                    queue_opts = ','.join(rule_conf['queue_options'])
                    output.append(f'{queue_opts}')

        # Synproxy
        if 'synproxy' in rule_conf:
            synproxy_mss = dict_search_args(rule_conf, 'synproxy', 'tcp', 'mss')
            if synproxy_mss:
                output.append(f'mss {synproxy_mss}')
            synproxy_ws = dict_search_args(rule_conf, 'synproxy', 'tcp', 'window_scale')
            if synproxy_ws:
                output.append(f'wscale {synproxy_ws} timestamp sack-perm')

    else:
        if set_table:
            output.append('return')

    output.append(f'comment "{family}-{hook}-{fw_name}-{rule_id}"')
    return " ".join(output)

def parse_gre_flags(flags, force_keyed=False):
    flag_map = { # nft does not have symbolic names for these. 
        'checksum': 1<<0,
        'routing':  1<<1,
        'key':      1<<2,
        'sequence': 1<<3,
        'strict_routing': 1<<4,
    }

    include = 0
    exclude = 0
    for fl_name, fl_state in flags.items():
        if not fl_state: 
            include |= flag_map[fl_name]
        else: # 'unset' child tag
            exclude |= flag_map[fl_name]

    if force_keyed:
        # Implied by a key-match.
        include |= flag_map['key']

    if include == 0 and exclude == 0:
        return '' # Don't bother extracting and matching no bits

    return f'gre flags & {include + exclude} == {include}'

def parse_tcp_flags(flags):
    include = [flag for flag in flags if flag != 'not']
    exclude = list(flags['not']) if 'not' in flags else []
    return f'tcp flags & ({"|".join(include + exclude)}) == {"|".join(include) if include else "0x0"}'

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

# GeoIP

nftables_geoip_conf = '/run/nftables-geoip.conf'
geoip_database = '/usr/share/vyos-geoip/dbip-country-lite.csv.gz'
geoip_lock_file = '/run/vyos-geoip.lock'

def geoip_load_data(codes=[]):
    data = None

    if not os.path.exists(geoip_database):
        return []

    try:
        with gzip.open(geoip_database, mode='rt') as csv_fh:
            reader = csv.reader(csv_fh)
            out = []
            for start, end, code in reader:
                if code.lower() in codes:
                    out.append([start, end, code.lower()])
            return out
    except:
        print('Error: Failed to open GeoIP database')
    return []

def geoip_download_data():
    url = 'https://download.db-ip.com/free/dbip-country-lite-{}.csv.gz'.format(strftime("%Y-%m"))
    try:
        dirname = os.path.dirname(geoip_database)
        if not os.path.exists(dirname):
            os.mkdir(dirname)

        download(geoip_database, url)
        print("Downloaded GeoIP database")
        return True
    except:
        print("Error: Failed to download GeoIP database")
    return False

class GeoIPLock(object):
    def __init__(self, file):
        self.file = file

    def __enter__(self):
        if os.path.exists(self.file):
            return False

        Path(self.file).touch()
        return True

    def __exit__(self, exc_type, exc_value, tb):
        os.unlink(self.file)

def geoip_update(firewall, force=False):
    with GeoIPLock(geoip_lock_file) as lock:
        if not lock:
            print("Script is already running")
            return False

        if not firewall:
            print("Firewall is not configured")
            return True

        if not os.path.exists(geoip_database):
            if not geoip_download_data():
                return False
        elif force:
            geoip_download_data()

        ipv4_codes = {}
        ipv6_codes = {}

        ipv4_sets = {}
        ipv6_sets = {}

        # Map country codes to set names
        for codes, path in dict_search_recursive(firewall, 'country_code'):
            set_name = f'GEOIP_CC_{path[1]}_{path[2]}_{path[4]}'
            if ( path[0] == 'ipv4'):
                for code in codes:
                    ipv4_codes.setdefault(code, []).append(set_name)
            elif ( path[0] == 'ipv6' ):
                set_name = f'GEOIP_CC6_{path[1]}_{path[2]}_{path[4]}'
                for code in codes:
                    ipv6_codes.setdefault(code, []).append(set_name)

        if not ipv4_codes and not ipv6_codes:
            if force:
                print("GeoIP not in use by firewall")
            return True

        geoip_data = geoip_load_data([*ipv4_codes, *ipv6_codes])

        # Iterate IP blocks to assign to sets
        for start, end, code in geoip_data:
            ipv4 = is_ipv4(start)
            if code in ipv4_codes and ipv4:
                ip_range = f'{start}-{end}' if start != end else start
                for setname in ipv4_codes[code]:
                    ipv4_sets.setdefault(setname, []).append(ip_range)
            if code in ipv6_codes and not ipv4:
                ip_range = f'{start}-{end}' if start != end else start
                for setname in ipv6_codes[code]:
                    ipv6_sets.setdefault(setname, []).append(ip_range)

        render(nftables_geoip_conf, 'firewall/nftables-geoip-update.j2', {
            'ipv4_sets': ipv4_sets,
            'ipv6_sets': ipv6_sets
        })

        result = run(f'nft --file {nftables_geoip_conf}')
        if result != 0:
            print('Error: GeoIP failed to update firewall')
            return False

        return True
