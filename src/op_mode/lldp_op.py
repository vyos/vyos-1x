#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
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

import argparse
import jinja2
import json

from sys import exit
from tabulate import tabulate

from vyos.util import cmd
from vyos.config import Config

parser = argparse.ArgumentParser()
parser.add_argument("-a", "--all", action="store_true", help="Show LLDP neighbors on all interfaces")
parser.add_argument("-d", "--detail", action="store_true", help="Show detailes LLDP neighbor information on all interfaces")
parser.add_argument("-i", "--interface", action="store", help="Show LLDP neighbors on specific interface")

# Please be careful if you edit the template.
lldp_out = """Capability Codes: R - Router, B - Bridge, W - Wlan r - Repeater, S - Station
                  D - Docsis, T - Telephone, O - Other

Device ID                 Local     Proto  Cap   Platform             Port ID
---------                 -----     -----  ---   --------             -------
{% for neighbor in neighbors %}
{%   for local_if, info in neighbor.items() %}
{{ "%-25s" | format(info.chassis) }} {{ "%-9s" | format(local_if) }} {{ "%-6s" | format(info.proto) }} {{ "%-5s" | format(info.capabilities) }} {{ "%-20s" | format(info.platform[:18]) }} {{ info.remote_if }}
{%   endfor %}
{% endfor %}
"""

def get_neighbors():
    return cmd('/usr/sbin/lldpcli -f json show neighbors')

def parse_data(data):
    output = []
    for local_if, values in data.items():
        for chassis, c_value in values.get('chassis', {}).items():
            capabilities = c_value['capability']
            if isinstance(capabilities, dict):
                capabilities = [capabilities]

            cap = ''
            for capability in capabilities:
                if capability['enabled']:
                    if capability['type'] == 'Router':
                        cap += 'R'
                    if capability['type'] == 'Bridge':
                        cap += 'B'
                    if capability['type'] == 'Wlan':
                        cap += 'W'
                    if capability['type'] == 'Station':
                        cap += 'S'
                    if capability['type'] == 'Repeater':
                        cap += 'r'
                    if capability['type'] == 'Telephone':
                        cap += 'T'
                    if capability['type'] == 'Docsis':
                        cap += 'D'
                    if capability['type'] == 'Other':
                        cap += 'O'


        remote_if = 'Unknown'
        if 'descr' in values.get('port', {}):
            remote_if = values.get('port', {}).get('descr')
        elif 'id' in values.get('port', {}):
            remote_if = values.get('port', {}).get('id').get('value', 'Unknown')

        output.append({local_if: {'chassis': chassis,
                                   'remote_if': remote_if,
                                   'proto': values.get('via','Unknown'),
                                   'platform': c_value.get('descr', 'Unknown'),
                                   'capabilities': cap}})


    output = {'neighbors': output}
    return output

if __name__ == '__main__':
    args = parser.parse_args()
    tmp = { 'neighbors' : [] }

    c = Config()
    if not c.exists_effective(['service', 'lldp']):
        print('Service LLDP is not configured')
        exit(0)

    if args.detail:
        print(cmd('/usr/sbin/lldpctl -f plain'))
        exit(0)
    elif args.all or args.interface:
        tmp = json.loads(get_neighbors())
        neighbors = dict()

        if 'interface' in tmp.get('lldp'):
            if args.all:
                neighbors = tmp['lldp']['interface']
            elif args.interface:
                if args.interface in tmp['lldp']['interface']:
                    neighbors[args.interface] = tmp['lldp']['interface'][args.interface]

    else:
        parser.print_help()
        exit(1)

    tmpl = jinja2.Template(lldp_out)
    config_text = tmpl.render(parse_data(neighbors))
    print(config_text)

    exit(0)
