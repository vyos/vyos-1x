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
    tmp = cmd('sudo nft -j list table ip6 nat')
    tmp = json.loads(tmp)
    
    format_nat66_rule = '{0: <10} {1: <50} {2: <50} {3: <10}'
    print(format_nat66_rule.format("Rule", "Source" if args.source else "Destination", "Translation", "Outbound Interface" if args.source else "Inbound Interface"))
    print(format_nat66_rule.format("----", "------" if args.source else "-----------", "-----------", "------------------" if args.source else "-----------------"))
    
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
        for comment_prefix in ['SRC-NAT66-', 'DST-NAT66-']:
            if comment_prefix in comment:
                continue_rule = False
        if continue_rule:
            continue
        
        # When log is detected from the second index of expr, then this rule should be ignored
        if 'log' in data['expr'][2]:
            continue
        
        rule = comment.replace('SRC-NAT66-','')
        rule = rule.replace('DST-NAT66-','')
        chain = data['chain']
        if not (args.source and chain == 'POSTROUTING') or (not args.source and chain == 'PREROUTING'):
            continue
        interface = dict_search('match.right', data['expr'][0])
        srcdest = dict_search('match.right.prefix.addr', data['expr'][2])
        if srcdest:
            addr_tmp = dict_search('match.right.prefix.len', data['expr'][2])
            if addr_tmp:
                srcdest = srcdest + '/' + str(addr_tmp)
        else:
            srcdest = dict_search('match.right', data['expr'][2])
        
        tran_addr = dict_search('snat.addr.prefix.addr' if args.source else 'dnat.addr.prefix.addr', data['expr'][3])
        if tran_addr:
            addr_tmp = dict_search('snat.addr.prefix.len' if args.source else 'dnat.addr.prefix.len', data['expr'][3])
            if addr_tmp:
                srcdest = srcdest + '/' + str(addr_tmp)
        else:
            if 'masquerade' in data['expr'][3]:
                tran_addr = 'masquerade'
            else:
                tran_addr = dict_search('snat.addr' if args.source else 'dnat.addr', data['expr'][3])
        
        print(format_nat66_rule.format(rule, srcdest, tran_addr, interface))
    
    exit(0)
else:
    parser.print_help()
    exit(1)

