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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import jmespath
import json

from argparse import ArgumentParser
from jinja2 import Template
from sys import exit
from vyos.util import cmd
from vyos.util import dict_search

parser = ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("--source", help="Show statistics for configured source NAT rules", action="store_true")
group.add_argument("--destination", help="Show statistics for configured destination NAT rules", action="store_true")
args = parser.parse_args()

if args.source or args.destination:
    tmp = cmd('sudo nft -j list table ip nat')
    tmp = json.loads(tmp)

    format_nat_rule = '{0: <10} {1: <50} {2: <50} {3: <10}'
    print(format_nat_rule.format("Rule", "Source" if args.source else "Destination", "Translation", "Outbound Interface" if args.source else "Inbound Interface"))
    print(format_nat_rule.format("----", "------" if args.source else "-----------", "-----------", "------------------" if args.source else "-----------------"))

    data_json = jmespath.search('nftables[?rule].rule[?chain]', tmp)
    for idx in range(0, len(data_json)):
        data = data_json[idx]

        # The following key values must exist
        # When the rule JSON does not have some keys, this is not a rule we can work with
        continue_rule = False
        for key in ['comment', 'chain', 'expr']:
            if key not in data:
                continue_rule = True
                continue
        if continue_rule:
            continue

        comment = data['comment']

        # Check the annotation to see if the annotation format is created by VYOS
        continue_rule = True
        for comment_prefix in ['SRC-NAT-', 'DST-NAT-']:
            if comment_prefix in comment:
                continue_rule = False
        if continue_rule:
            continue

        rule = int(''.join(list(filter(str.isdigit, comment))))
        chain = data['chain']
        if not ((args.source and chain == 'POSTROUTING') or (not args.source and chain == 'PREROUTING')):
            continue
        interface = dict_search('match.right', data['expr'][0])
        srcdest = ''
        srcdests = []
        tran_addr = ''
        for i in range(1,len(data['expr']) ):
            srcdest_json = dict_search('match.right', data['expr'][i])
            if srcdest_json:
                if isinstance(srcdest_json,str):
                    if srcdest != '':
                        srcdests.append(srcdest)
                        srcdest = ''
                    srcdest = srcdest_json + ' '
                elif 'prefix' in srcdest_json:
                    addr_tmp = dict_search('match.right.prefix.addr', data['expr'][i])
                    len_tmp = dict_search('match.right.prefix.len', data['expr'][i])
                    if addr_tmp and len_tmp:
                        srcdest = addr_tmp + '/' + str(len_tmp) + ' '
                elif 'set' in srcdest_json:
                    if isinstance(srcdest_json['set'][0],int):
                        srcdest += 'port ' + str(srcdest_json['set'][0]) + ' '
                    else:
                        port_range = srcdest_json['set'][0]['range']
                        srcdest += 'port ' + str(port_range[0]) + '-' + str(port_range[1]) + ' '

            tran_addr_json = dict_search('snat' if args.source else 'dnat', data['expr'][i])
            if tran_addr_json:
                if isinstance(tran_addr_json['addr'],str):
                    tran_addr += tran_addr_json['addr'] + ' '
                elif 'prefix' in tran_addr_json['addr']:
                    addr_tmp = dict_search('snat.addr.prefix.addr' if args.source else 'dnat.addr.prefix.addr', data['expr'][3])
                    len_tmp = dict_search('snat.addr.prefix.len' if args.source else 'dnat.addr.prefix.len', data['expr'][3])
                    if addr_tmp and len_tmp:
                        tran_addr += addr_tmp + '/' + str(len_tmp) + ' '

                if isinstance(tran_addr_json['port'],int):
                    tran_addr += 'port ' + str(tran_addr_json['port'])

            else:
                if 'masquerade' in data['expr'][i]:
                    tran_addr = 'masquerade'
                elif 'log' in data['expr'][i]:
                    continue

        if srcdest != '':
            srcdests.append(srcdest)
            srcdest = ''
        print(format_nat_rule.format(rule, srcdests[0], tran_addr, interface))

        for i in range(1, len(srcdests)):
            print(format_nat_rule.format(' ', srcdests[i], ' ', ' '))

    exit(0)
else:
    parser.print_help()
    exit(1)

