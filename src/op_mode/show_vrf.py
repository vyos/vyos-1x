#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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
from json import loads

from vyos.util import cmd

vrf_out_tmpl = """
VRF name          state     mac address        flags                     interfaces
--------          -----     -----------        -----                     ----------
{% for v in vrf %}
{{"%-16s"|format(v.ifname)}}  {{ "%-8s"|format(v.operstate | lower())}}  {{"%-17s"|format(v.address | lower())}}  {{ v.flags|join(',')|lower()}}  {{v.members|join(',')|lower()}}
{% endfor %}

"""

def list_vrfs():
    command = 'ip -j -br link show type vrf'
    answer = loads(cmd(command))
    return [_ for _ in answer if _]

def list_vrf_members(vrf):
    command = f'ip -j -br link show master {vrf}'
    answer = loads(cmd(command))
    return [_ for _ in answer if _]

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("-e", "--extensive", action="store_true",
                   help="provide detailed vrf informatio")
parser.add_argument('interface', metavar='I', type=str, nargs='?',
                    help='interface to display')

args = parser.parse_args()

if args.extensive:
    data = { 'vrf': [] }
    for vrf in list_vrfs():
        name = vrf['ifname']
        if args.interface and name != args.interface:
            continue

        vrf['members'] = []
        for member in list_vrf_members(name):
            vrf['members'].append(member['ifname'])
        data['vrf'].append(vrf)

    tmpl = jinja2.Template(vrf_out_tmpl)
    print(tmpl.render(data))

else:
    print(" ".join([vrf['ifname'] for vrf in list_vrfs()]))
