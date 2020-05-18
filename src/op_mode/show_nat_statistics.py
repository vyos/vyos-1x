#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
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
from vyos.command import cmd

OUT_TMPL_SRC="""
rule      pkts        bytes   interface
----      ----        -----   ---------
{% for r in output %}
{%- if r.comment -%}
{%- set packets   = r.counter.packets -%}
{%- set bytes     = r.counter.bytes -%}
{%- set interface = r.interface -%}
{# remove rule comment prefix #}
{%- set comment   = r.comment | replace('SRC-NAT-', '') | replace('DST-NAT-', '') | replace(' tcp_udp', '') -%}
{{ "%-4s" | format(comment) }} {{ "%9s" | format(packets) }} {{ "%12s" | format(bytes) }}   {{ interface }}
{%- endif %}
{% endfor %}
"""

parser = ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("--source", help="Show statistics for configured source NAT rules", action="store_true")
group.add_argument("--destination", help="Show statistics for configured destination NAT rules", action="store_true")
args = parser.parse_args()

if args.source or args.destination:
    tmp = cmd('sudo nft -j list table nat')
    tmp = json.loads(tmp)

    source = r"nftables[?rule.chain=='POSTROUTING'].rule.{chain: chain, handle: handle, comment: comment, counter: expr[].counter | [0], interface: expr[].match.right | [0] }"
    destination = r"nftables[?rule.chain=='PREROUTING'].rule.{chain: chain, handle: handle, comment: comment, counter: expr[].counter | [0], interface: expr[].match.right | [0] }"
    data = {
        'output' : jmespath.search(source if args.source else destination, tmp),
        'direction' : 'source' if args.source else 'destination'
    }

    tmpl = Template(OUT_TMPL_SRC, lstrip_blocks=True)
    print(tmpl.render(data))
    exit(0)
else:
    parser.print_help()
    exit(1)

