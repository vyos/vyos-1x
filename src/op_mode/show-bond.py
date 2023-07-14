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

import jinja2

from argparse import ArgumentParser
from vyos.ifconfig import Section
from vyos.ifconfig import BondIf
from vyos.utils.file import read_file

from sys import exit

parser = ArgumentParser()
parser.add_argument("--slaves", action="store_true", help="Show LLDP neighbors on all interfaces")
parser.add_argument("--interface", action="store", help="Show LLDP neighbors on specific interface")

args = parser.parse_args()

all_bonds = Section.interfaces('bonding')
# we are not interested in any bond vlan interface
all_bonds = [x for x in all_bonds if '.' not in x]

TMPL_BRIEF = """Interface    Mode                   State    Link   Slaves
{% for interface in data %}
{{ "%-12s" | format(interface.ifname) }} {{ "%-22s" | format(interface.mode) }} {{ "%-8s" | format(interface.admin_state) }} {{ "%-6s" | format(interface.oper_state) }} {{ interface.members | join(' ') }}
{% endfor %}
"""

TMPL_INDIVIDUAL_BOND = """Interface        RX: bytes  packets     TX: bytes  packets
{{ "%-16s" | format(data.ifname) }} {{ "%-10s" | format(data.rx_bytes) }} {{ "%-11s" | format(data.rx_packets) }} {{ "%-10s" | format(data.tx_bytes) }} {{ data.tx_packets }}
{% for member in data.members if data.members is defined %}
    {{ "%-12s" | format(member.ifname) }} {{ "%-10s" | format(member.rx_bytes) }} {{ "%-11s" | format(member.rx_packets) }} {{ "%-10s" | format(member.tx_bytes) }} {{ member.tx_packets }}
{% endfor %}
"""

if args.slaves and args.interface:
    exit('Can not use both --slaves and --interfaces option at the same time')
    parser.print_help()

elif args.slaves:
    data = []
    template = TMPL_BRIEF
    for bond in all_bonds:
        tmp = BondIf(bond)
        cfg_dict = {}
        cfg_dict['ifname'] = bond
        cfg_dict['mode'] = tmp.get_mode()
        cfg_dict['admin_state'] = tmp.get_admin_state()
        cfg_dict['oper_state'] = tmp.operational.get_state()
        cfg_dict['members'] = tmp.get_slaves()
        data.append(cfg_dict)

elif args.interface:
    template = TMPL_INDIVIDUAL_BOND
    data = {}
    data['ifname'] = args.interface
    data['rx_bytes'] = read_file(f'/sys/class/net/{args.interface}/statistics/rx_bytes')
    data['rx_packets'] = read_file(f'/sys/class/net/{args.interface}/statistics/rx_packets')
    data['tx_bytes'] = read_file(f'/sys/class/net/{args.interface}/statistics/tx_bytes')
    data['tx_packets'] = read_file(f'/sys/class/net/{args.interface}/statistics/tx_packets')

    # each bond member interface has its own statistics
    data['members'] = []
    for member in BondIf(args.interface).get_slaves():
        tmp = {}
        tmp['ifname'] = member
        tmp['rx_bytes'] = read_file(f'/sys/class/net/{member}/statistics/rx_bytes')
        tmp['rx_packets'] = read_file(f'/sys/class/net/{member}/statistics/rx_packets')
        tmp['tx_bytes'] = read_file(f'/sys/class/net/{member}/statistics/tx_bytes')
        tmp['tx_packets'] = read_file(f'/sys/class/net/{member}/statistics/tx_packets')
        data['members'].append(tmp)

else:
    parser.print_help()
    exit(1)

tmpl = jinja2.Template(template, trim_blocks=True)
config_text = tmpl.render(data=data)
print(config_text)
