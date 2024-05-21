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
from vyos.utils.dict import dict_search_args
from vyos.template import bracketize_ipv6


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
        operator = ''
        if 'name' in rule_conf['inbound_interface']:
            iiface = rule_conf['inbound_interface']['name']
            if iiface[0] == '!':
                operator = '!='
                iiface = iiface[1:]
            output.append(f'iifname {operator} {{{iiface}}}')
        else:
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
        else:
            oiface = rule_conf['outbound_interface']['group']
            if oiface[0] == '!':
                operator = '!='
                oiface = oiface[1:]
            output.append(f'oifname {operator} @I_{oiface}')

    if 'protocol' in rule_conf and rule_conf['protocol'] != 'all':
        protocol = rule_conf['protocol']
        if protocol == 'tcp_udp':
            protocol = '{ tcp, udp }'
        output.append(f'meta l4proto {protocol}')

    if 'packet_type' in rule_conf:
        output.append(f'pkttype ' + rule_conf['packet_type'])

    if 'exclude' in rule_conf:
        translation_str = 'return'
        log_suffix = '-EXCL'
    elif 'translation' in rule_conf:
        addr = dict_search_args(rule_conf, 'translation', 'address')
        port = dict_search_args(rule_conf, 'translation', 'port')
        if 'redirect' in rule_conf['translation']:
            translation_output = [f'redirect']
            redirect_port = dict_search_args(rule_conf, 'translation', 'redirect', 'port')
            if redirect_port:
                translation_output.append(f'to {redirect_port}')
        else:

            translation_prefix = nat_type[:1]
            translation_output = [f'{translation_prefix}nat']

            if addr and is_ip_network(addr):
                if not ipv6:
                    map_addr =  dict_search_args(rule_conf, nat_type, 'address')
                    if map_addr:
                        if port:
                            translation_output.append(f'{ip_prefix} prefix to {ip_prefix} {translation_prefix}addr map {{ {map_addr} : {addr} . {port} }}')
                        else:
                            translation_output.append(f'{ip_prefix} prefix to {ip_prefix} {translation_prefix}addr map {{ {map_addr} : {addr} }}')
                        ignore_type_addr = True
                    else:
                        translation_output.append(f'prefix to {addr}')
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
                    addr = bracketize_ipv6(addr)
                    translation_output.append(addr)

        options = []
        addr_mapping = dict_search_args(rule_conf, 'translation', 'options', 'address_mapping')
        port_mapping = dict_search_args(rule_conf, 'translation', 'options', 'port_mapping')
        if addr_mapping == 'persistent':
            options.append('persistent')
        if port_mapping and port_mapping != 'none':
            options.append(port_mapping)

        if ((not addr) or (addr and not is_ip_network(addr))) and port:
            translation_str = " ".join(translation_output) + (f':{port}')
        else:
            translation_str = " ".join(translation_output)

        if options:
            translation_str += f' {",".join(options)}'

        if not ipv6 and 'backend' in rule_conf['load_balance']:
            hash_input_items = []
            current_prob = 0
            nat_map = []

            for trans_addr, addr in rule_conf['load_balance']['backend'].items():
                item_prob = int(addr['weight'])
                upper_limit = current_prob + item_prob - 1
                hash_val = str(current_prob) + '-' + str(upper_limit)
                element = hash_val + " : " + trans_addr
                nat_map.append(element)
                current_prob = current_prob + item_prob

            elements = ' , '.join(nat_map)

            if 'hash' in rule_conf['load_balance'] and 'random' in rule_conf['load_balance']['hash']:
                translation_str += ' numgen random mod 100 map ' + '{ ' + f'{elements}' + ' }'
            else:
                for input_param in rule_conf['load_balance']['hash']:
                    if input_param == 'source-address':
                        param = 'ip saddr'
                    elif input_param == 'destination-address':
                        param = 'ip daddr'
                    elif input_param == 'source-port':
                        prot = rule_conf['protocol']
                        param = f'{prot} sport'
                    elif input_param == 'destination-port':
                        prot = rule_conf['protocol']
                        param = f'{prot} dport'
                    hash_input_items.append(param)
                hash_input = ' . '.join(hash_input_items)
                translation_str += f' jhash ' + f'{hash_input}' + ' mod 100 map ' + '{ ' + f'{elements}' + ' }'

    for target in ['source', 'destination']:
        if target not in rule_conf:
            continue

        side_conf = rule_conf[target]
        prefix = target[:1]

        addr = dict_search_args(side_conf, 'address')
        if addr and not (ignore_type_addr and target == nat_type):
            operator = ''
            if addr[:1] == '!':
                operator = '!='
                addr = addr[1:]
            output.append(f'{ip_prefix} {prefix}addr {operator} {addr}')

        addr_prefix = dict_search_args(side_conf, 'prefix')
        if addr_prefix and ipv6:
            operator = ''
            if addr_prefix[:1] == '!':
                operator = '!='
                addr_prefix = addr_prefix[1:]
            output.append(f'ip6 {prefix}addr {operator} {addr_prefix}')

        port = dict_search_args(side_conf, 'port')
        if port:
            protocol = rule_conf['protocol']
            if protocol == 'tcp_udp':
                protocol = 'th'
            operator = ''
            if port[:1] == '!':
                operator = '!='
                port = port[1:]
            output.append(f'{protocol} {prefix}port {operator} {{ {port} }}')

        if 'group' in side_conf:
            group = side_conf['group']
            if 'address_group' in group and not (ignore_type_addr and target == nat_type):
                group_name = group['address_group']
                operator = ''
                if group_name[0] == '!':
                    operator = '!='
                    group_name = group_name[1:]
                output.append(f'{ip_prefix} {prefix}addr {operator} @A_{group_name}')
            # Generate firewall group domain-group
            elif 'domain_group' in group and not (ignore_type_addr and target == nat_type):
                group_name = group['domain_group']
                operator = ''
                if group_name[0] == '!':
                    operator = '!='
                    group_name = group_name[1:]
                output.append(f'{ip_prefix} {prefix}addr {operator} @D_{group_name}')
            elif 'network_group' in group and not (ignore_type_addr and target == nat_type):
                group_name = group['network_group']
                operator = ''
                if group_name[0] == '!':
                    operator = '!='
                    group_name = group_name[1:]
                output.append(f'{ip_prefix} {prefix}addr {operator} @N_{group_name}')
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

    if 'log' in rule_conf:
        output.append(f'log prefix "[{log_prefix}{log_suffix}]"')

    if translation_str:
        output.append(translation_str)

    output.append(f'comment "{log_prefix}"')

    return " ".join(output)
