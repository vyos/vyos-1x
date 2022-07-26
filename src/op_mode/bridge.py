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
import sys

from sys import exit
from tabulate import tabulate

from vyos.util import cmd
from vyos.util import dict_search

import vyos.opmode


def _get_json_data():
    """
    Get bridge data format JSON
    """
    return cmd(f'sudo bridge --json link show')


def _get_raw_data_summary():
    """Get interested rules
    :returns dict
    """
    data = _get_json_data()
    data_dict = json.loads(data)
    return data_dict


def _get_bridge_members(bridge: str) -> list:
    """
    Get list of interface bridge members
    :param bridge: str
    :default: ['n/a']
    :return: list
    """
    data = _get_raw_data_summary()
    members = jmespath.search(f'[?master == `{bridge}`].ifname', data)
    return [member for member in members] if members else ['n/a']


def _get_member_options(bridge: str):
    data = _get_raw_data_summary()
    options = jmespath.search(f'[?master == `{bridge}`]', data)
    return options


def _get_formatted_output_summary(data):
    data_entries = ''
    bridges = set(jmespath.search('[*].master', data))
    for bridge in bridges:
        member_options = _get_member_options(bridge)
        member_entries = []
        for option in member_options:
            interface = option.get('ifname')
            ifindex = option.get('ifindex')
            state = option.get('state')
            mtu = option.get('mtu')
            flags = ','.join(option.get('flags')).lower()
            prio = option.get('priority')
            member_entries.append([interface, state, mtu, flags, prio])
        member_headers = ["Member", "State", "MTU", "Flags", "Prio"]
        output_members = tabulate(member_entries, member_headers, numalign="left")
        output_bridge = f"""Bridge interface {bridge}:
{output_members}

"""
        data_entries += output_bridge
    output = data_entries
    return output


def show(raw: bool):
    bridge_data = _get_raw_data_summary()
    if raw:
        return bridge_data
    else:
        return _get_formatted_output_summary(bridge_data)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except ValueError as e:
        print(e)
        sys.exit(1)
