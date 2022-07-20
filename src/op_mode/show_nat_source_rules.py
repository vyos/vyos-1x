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

from argparse import ArgumentParser
from sys import exit
from tabulate import tabulate

from vyos.util import cmd
from vyos.util import dict_search


parser = ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("--source", help="Show statistics for configured source NAT rules", action="store_true")
group.add_argument("--destination", help="Show statistics for configured destination NAT rules", action="store_true")
args = parser.parse_args()

direction = 'source' if args.source else 'destination'


def _get_raw_data(direction):
    """
    Get NAT format JSON
    """
    if direction == 'source':
        chain = 'POSTROUTING'
    if direction == 'destination':
        chain = 'PREROUTING'
    return cmd(f'sudo nft --json list chain ip nat {chain}')


def _get_rules(data):
    """Get interested rules
    :returns dict
    """
    return [rule for rule in data['nftables'] if 'rule' in rule and 'comment' in rule['rule']]


def _get_formatted_output():
    raw_data = json.loads(_get_raw_data(direction))
    data = _get_rules(raw_data)
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
                if 'prefix' in match['right'] or 'set' in match['right']:
                    # Merge dict src/dst l3_l4 parameters
                    my_dict = {**match['left']['payload'], **match['right']}
                    proto = my_dict.get('protocol').upper()
                    if my_dict['field'] == 'saddr':
                        saddr = f'{my_dict["prefix"]["addr"]}/{my_dict["prefix"]["len"]}'
                    elif my_dict['field'] == 'daddr':
                        daddr = f'{my_dict["prefix"]["addr"]}/{my_dict["prefix"]["len"]}'

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
                    if jmespath.search('left.payload.field', match) == 'saddr':
                        saddr = match.get('right')
                    if jmespath.search('left.payload.field', match) == 'daddr':
                        daddr = match.get('right')
            else:
                saddr = '0.0.0.0/0'
                daddr = '0.0.0.0/0'
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


def show(raw: bool):
    nat_data = _get_raw_data(direction)
    if raw:
        return nat_data
    else:
        return _get_formatted_output()


if __name__ == '__main__':
    print(show(raw=False))
