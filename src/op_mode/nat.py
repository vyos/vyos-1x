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

import jmespath
import json
import sys
import xmltodict

from sys import exit
from tabulate import tabulate

from vyos.util import cmd
from vyos.util import dict_search

import vyos.opmode


def _get_xml_translation(direction, family):
    """
    Get conntrack XML output --src-nat|--dst-nat
    """
    if direction == 'source':
        opt = '--src-nat'
    if direction == 'destination':
        opt = '--dst-nat'
    return cmd(f'sudo conntrack --dump --family {family} {opt} --output xml')


def _xml_to_dict(xml):
    """
    Convert XML to dictionary
    Return: dictionary
    """
    parse = xmltodict.parse(xml, attr_prefix='')
    # If only one conntrack entry we must change dict
    if 'meta' in parse['conntrack']['flow']:
        return dict(conntrack={'flow': [parse['conntrack']['flow']]})
    return parse


def _get_json_data(direction, family):
    """
    Get NAT format JSON
    """
    if direction == 'source':
        chain = 'POSTROUTING'
    if direction == 'destination':
        chain = 'PREROUTING'
    family = 'ip6' if family == 'inet6' else 'ip'
    return cmd(f'sudo nft --json list chain {family} vyos_nat {chain}')


def _get_raw_data_rules(direction, family):
    """Get interested rules
    :returns dict
    """
    data = _get_json_data(direction, family)
    data_dict = json.loads(data)
    rules = []
    for rule in data_dict['nftables']:
        if 'rule' in rule and 'comment' in rule['rule']:
            rules.append(rule)
    return rules


def _get_raw_translation(direction, family):
    """
    Return: dictionary
    """
    xml = _get_xml_translation(direction, family)
    if len(xml) == 0:
        output = {'conntrack':
            {
                'error': True,
                'reason': 'entries not found'
            }
        }
        return output
    return _xml_to_dict(xml)


def _get_formatted_output_rules(data, direction, family):
    # Add default values before loop
    sport, dport, proto = 'any', 'any', 'any'
    saddr = '::/0' if family == 'inet6' else '0.0.0.0/0'
    daddr = '::/0' if family == 'inet6' else '0.0.0.0/0'

    data_entries = []
    for rule in data:
        if 'comment' in rule['rule']:
            comment = rule.get('rule').get('comment')
            rule_number = comment.split('-')[-1]
            rule_number = rule_number.split(' ')[0]
        if 'expr' in rule['rule']:
            interface = rule.get('rule').get('expr')[0].get('match').get('right') \
                if jmespath.search('rule.expr[*].match.left.meta', rule) else 'any'
        for index, match in enumerate(jmespath.search('rule.expr[*].match', rule)):
            if 'payload' in match['left']:
                if isinstance(match['right'], dict) and ('prefix' in match['right'] or 'set' in match['right']):
                    # Merge dict src/dst l3_l4 parameters
                    my_dict = {**match['left']['payload'], **match['right']}
                    my_dict['op'] = match['op']
                    op = '!' if my_dict.get('op') == '!=' else ''
                    proto = my_dict.get('protocol').upper()
                    if my_dict['field'] == 'saddr':
                        saddr = f'{op}{my_dict["prefix"]["addr"]}/{my_dict["prefix"]["len"]}'
                    elif my_dict['field'] == 'daddr':
                        daddr = f'{op}{my_dict["prefix"]["addr"]}/{my_dict["prefix"]["len"]}'
                    elif my_dict['field'] == 'sport':
                        # Port range or single port
                        if jmespath.search('set[*].range', my_dict):
                            sport = my_dict['set'][0]['range']
                            sport = '-'.join(map(str, sport))
                        else:
                            sport = my_dict.get('set')
                            sport = ','.join(map(str, sport))
                    elif my_dict['field'] == 'dport':
                        # Port range or single port
                        if jmespath.search('set[*].range', my_dict):
                            dport = my_dict["set"][0]["range"]
                            dport = '-'.join(map(str, dport))
                        else:
                            dport = my_dict.get('set')
                            dport = ','.join(map(str, dport))
                else:
                    field = jmespath.search('left.payload.field', match)
                    if field == 'saddr':
                        saddr = match.get('right')
                    elif field == 'daddr':
                        daddr = match.get('right')
                    elif field == 'sport':
                        sport = match.get('right')
                    elif field == 'dport':
                        dport = match.get('right')
            else:
                saddr = '::/0' if family == 'inet6' else '0.0.0.0/0'
                daddr = '::/0' if family == 'inet6' else '0.0.0.0/0'
                sport = 'any'
                dport = 'any'
                proto = 'any'

            source = f'''{saddr}
sport {sport}'''
            destination = f'''{daddr}
dport {dport}'''

            if jmespath.search('left.payload.field', match) == 'protocol':
                field_proto = match.get('right').upper()

            for expr in rule.get('rule').get('expr'):
                if 'snat' in expr:
                    translation = dict_search('snat.addr', expr)
                    if expr['snat'] and 'port' in expr['snat']:
                        if jmespath.search('snat.port.range', expr):
                            port = dict_search('snat.port.range', expr)
                            port = '-'.join(map(str, port))
                        else:
                            port = expr['snat']['port']
                        translation = f'''{translation}
port {port}'''

                elif 'masquerade' in expr:
                    translation = 'masquerade'
                    if expr['masquerade'] and 'port' in expr['masquerade']:
                        if jmespath.search('masquerade.port.range', expr):
                            port = dict_search('masquerade.port.range', expr)
                            port = '-'.join(map(str, port))
                        else:
                            port = expr['masquerade']['port']

                        translation = f'''{translation}
port {port}'''
                elif 'dnat' in expr:
                    translation = dict_search('dnat.addr', expr)
                    if expr['dnat'] and 'port' in expr['dnat']:
                        if jmespath.search('dnat.port.range', expr):
                            port = dict_search('dnat.port.range', expr)
                            port = '-'.join(map(str, port))
                        else:
                            port = expr['dnat']['port']
                        translation = f'''{translation}
port {port}'''
                else:
                    translation = 'exclude'
        # Overwrite match loop 'proto' if specified filed 'protocol' exist
        if 'protocol' in jmespath.search('rule.expr[*].match.left.payload.field', rule):
            proto = jmespath.search('rule.expr[0].match.right', rule).upper()

        data_entries.append([rule_number, source, destination, proto, interface, translation])

    interface_header = 'Out-Int' if direction == 'source' else 'In-Int'
    headers = ["Rule", "Source", "Destination", "Proto", interface_header, "Translation"]
    output = tabulate(data_entries, headers, numalign="left")
    return output


def _get_formatted_output_statistics(data, direction):
    data_entries = []
    for rule in data:
        if 'comment' in rule['rule']:
            comment = rule.get('rule').get('comment')
            rule_number = comment.split('-')[-1]
            rule_number = rule_number.split(' ')[0]
        if 'expr' in rule['rule']:
            interface = rule.get('rule').get('expr')[0].get('match').get('right') \
                if jmespath.search('rule.expr[*].match.left.meta', rule) else 'any'
            packets = jmespath.search('rule.expr[*].counter.packets | [0]', rule)
            _bytes = jmespath.search('rule.expr[*].counter.bytes | [0]', rule)
        data_entries.append([rule_number, packets, _bytes, interface])
    headers = ["Rule", "Packets", "Bytes", "Interface"]
    output = tabulate(data_entries, headers, numalign="left")
    return output


def _get_formatted_translation(dict_data, nat_direction, family):
    data_entries = []
    if 'error' in dict_data['conntrack']:
        return 'Entries not found'
    for entry in dict_data['conntrack']['flow']:
        orig_src, orig_dst, orig_sport, orig_dport = {}, {}, {}, {}
        reply_src, reply_dst, reply_sport, reply_dport = {}, {}, {}, {}
        proto = {}
        for meta in entry['meta']:
            direction = meta['direction']
            if direction in ['original']:
                if 'layer3' in meta:
                    orig_src = meta['layer3']['src']
                    orig_dst = meta['layer3']['dst']
                if 'layer4' in meta:
                    if meta.get('layer4').get('sport'):
                        orig_sport = meta['layer4']['sport']
                    if meta.get('layer4').get('dport'):
                        orig_dport = meta['layer4']['dport']
                    proto = meta['layer4']['protoname']
            if direction in ['reply']:
                if 'layer3' in meta:
                    reply_src = meta['layer3']['src']
                    reply_dst = meta['layer3']['dst']
                if 'layer4' in meta:
                    if meta.get('layer4').get('sport'):
                        reply_sport = meta['layer4']['sport']
                    if meta.get('layer4').get('dport'):
                        reply_dport = meta['layer4']['dport']
                    proto = meta['layer4']['protoname']
            if direction == 'independent':
                conn_id = meta['id']
                timeout = meta['timeout']
                orig_src = f'{orig_src}:{orig_sport}' if orig_sport else orig_src
                orig_dst = f'{orig_dst}:{orig_dport}' if orig_dport else orig_dst
                reply_src = f'{reply_src}:{reply_sport}' if reply_sport else reply_src
                reply_dst = f'{reply_dst}:{reply_dport}' if reply_dport else reply_dst
                state = meta['state'] if 'state' in meta else ''
                mark = meta['mark']
                zone = meta['zone'] if 'zone' in meta else ''
                if nat_direction == 'source':
                    data_entries.append(
                        [orig_src, reply_dst, proto, timeout, mark, zone])
                elif nat_direction == 'destination':
                    data_entries.append(
                        [orig_dst, reply_src, proto, timeout, mark, zone])

    headers = ["Pre-NAT", "Post-NAT", "Proto", "Timeout", "Mark", "Zone"]
    output = tabulate(data_entries, headers, numalign="left")
    return output


def show_rules(raw: bool, direction: str, family: str):
    nat_rules = _get_raw_data_rules(direction, family)
    if raw:
        return nat_rules
    else:
        return _get_formatted_output_rules(nat_rules, direction, family)


def show_statistics(raw: bool, direction: str, family: str):
    nat_statistics = _get_raw_data_rules(direction, family)
    if raw:
        return nat_statistics
    else:
        return _get_formatted_output_statistics(nat_statistics, direction)


def show_translations(raw: bool, direction: str, family: str):
    family = 'ipv6' if family == 'inet6' else 'ipv4'
    nat_translation = _get_raw_translation(direction, family)
    if raw:
        return nat_translation
    else:
        return _get_formatted_translation(nat_translation, direction, family)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
