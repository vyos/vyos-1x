#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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

import json
import sys
import typing

from tabulate import tabulate
from vyos.utils.process import cmd

import vyos.opmode

ArgFamily = typing.Literal['inet', 'inet6']

def _get_raw_data(family, interface=None):
    tmp = 'ip -4'
    if family == 'inet6':
        tmp = 'ip -6'
    tmp = f'{tmp} -j maddr show'
    if interface:
        tmp = f'{tmp} dev {interface}'
    output = cmd(tmp)
    data = json.loads(output)
    if not data:
        return []
    return data

def _get_formatted_output(raw_data):
    data_entries = []

    # sort result by interface name
    for interface in sorted(raw_data, key=lambda x: x['ifname']):
        for address in interface['maddr']:
            tmp = []
            tmp.append(interface['ifname'])
            tmp.append(address['family'])
            tmp.append(address['address'])

            data_entries.append(tmp)

    headers = ["Interface", "Family", "Address"]
    output = tabulate(data_entries, headers, numalign="left")
    return output

def show_group(raw: bool, family: ArgFamily, interface: typing.Optional[str]):
    multicast_data = _get_raw_data(family=family, interface=interface)
    if raw:
        return multicast_data
    else:
        return _get_formatted_output(multicast_data)

if __name__ == "__main__":
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
