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

from subprocess import check_output
from json import loads

def list_vrfs():
    command = 'ip -j -br link show type vrf'
    answer = loads(check_output(command.split()).decode())
    return [_ for _ in answer if _]

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("-e", "--extensive", action="store_true",
                   help="provide detailed vrf informatio")
parser.add_argument('interface', metavar='I', type=str, nargs='?',
                    help='interface to display')

args = parser.parse_args()

if args.extensive:
    print('{:16}  {:7}  {:17}  {}'.format('interface', 'state', 'mac', 'flags'))
    print('{:16}  {:7}  {:17}  {}'.format('---------', '-----', '---', '-----'))
    for vrf in list_vrfs():
        name = vrf['ifname']
        if args.interface and name != args.interface:
            continue
        state = vrf['operstate'].lower()
        mac = vrf['address'].lower()
        info = ','.join([_.lower() for _ in vrf['flags']])
        print(f'{name:16}  {state:7}  {mac:17}  {info}')
else:
    print(" ".join([vrf['ifname'] for vrf in list_vrfs()]))
