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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import sys

from tabulate import tabulate
from vyos.util import cmd

import vyos.opmode


def _get_raw_data():
    """
    :return: list
    """
    output = cmd('sudo ip --json --brief link show type vrf')
    data = json.loads(output)
    return data


def _get_vrf_members(vrf: str) -> list:
    """
    Get list of interface VRF members
    :param vrf: str
    :return: list
    """
    output = cmd(f'sudo ip --json --brief link show master {vrf}')
    answer = json.loads(output)
    interfaces = []
    for data in answer:
        if 'ifname' in data:
            interfaces.append(data.get('ifname'))
    return interfaces if len(interfaces) > 0 else ['n/a']


def _get_formatted_output(raw_data):
    data_entries = []
    for vrf in raw_data:
        name = vrf.get('ifname')
        state = vrf.get('operstate').lower()
        hw_address = vrf.get('address')
        flags = ','.join(vrf.get('flags')).lower()
        members = ','.join(_get_vrf_members(name))
        data_entries.append([name, state, hw_address, flags, members])

    headers = ["Name", "State", "MAC address", "Flags", "Interfaces"]
    output = tabulate(data_entries, headers, numalign="left")
    return output


def show(raw: bool):
    vrf_data = _get_raw_data()
    if raw:
        return vrf_data
    else:
        return _get_formatted_output(vrf_data)


if __name__ == "__main__":
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except ValueError as e:
        print(e)
        sys.exit(1)
