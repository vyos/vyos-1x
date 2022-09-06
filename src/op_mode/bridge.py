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
import typing

from sys import exit
from tabulate import tabulate

from vyos.util import cmd, rc_cmd
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


def _get_raw_data_vlan():
    """
    :returns dict
    """
    json_data = cmd('sudo bridge --json --compressvlans vlan show')
    data_dict = json.loads(json_data)
    return data_dict


def _get_raw_data_fdb(bridge):
    """Get MAC-address for the bridge brX
    :returns list
    """
    code, json_data = rc_cmd(f'sudo bridge --json fdb show br {bridge}')
    # From iproute2 fdb.c, fdb_show() will only exit(-1) in case of
    # non-existent bridge device; raise error.
    if code == 255:
        raise vyos.opmode.UnconfiguredSubsystem(f"no such bridge device {bridge}")
    data_dict = json.loads(json_data)
    return data_dict


def _get_raw_data_mdb(bridge):
    """Get MAC-address multicast gorup for the bridge brX
    :return list
    """
    json_data = cmd(f'bridge --json  mdb show br {bridge}')
    data_dict = json.loads(json_data)
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


def _get_formatted_output_vlan(data):
    data_entries = []
    for entry in data:
        interface = entry.get('ifname')
        vlans = entry.get('vlans')
        for vlan_entry in vlans:
            vlan = vlan_entry.get('vlan')
            if vlan_entry.get('vlanEnd'):
                vlan_end = vlan_entry.get('vlanEnd')
                vlan = f'{vlan}-{vlan_end}'
            flags = ', '.join(vlan_entry.get('flags')).lower()
            data_entries.append([interface, vlan, flags])

    headers = ["Interface", "Vlan", "Flags"]
    output = tabulate(data_entries, headers)
    return output


def _get_formatted_output_fdb(data):
    data_entries = []
    for entry in data:
        interface = entry.get('ifname')
        mac = entry.get('mac')
        state = entry.get('state')
        flags = ','.join(entry['flags'])
        data_entries.append([interface, mac, state, flags])

    headers = ["Interface", "Mac address", "State", "Flags"]
    output = tabulate(data_entries, headers, numalign="left")
    return output


def _get_formatted_output_mdb(data):
    data_entries = []
    for entry in data:
        for mdb_entry in entry['mdb']:
            interface = mdb_entry.get('port')
            group = mdb_entry.get('grp')
            state = mdb_entry.get('state')
            flags = ','.join(mdb_entry.get('flags'))
            data_entries.append([interface, group, state, flags])
    headers = ["Interface", "Group", "State", "Flags"]
    output = tabulate(data_entries, headers)
    return output


def show(raw: bool):
    bridge_data = _get_raw_data_summary()
    if raw:
        return bridge_data
    else:
        return _get_formatted_output_summary(bridge_data)


def show_vlan(raw: bool):
    bridge_vlan = _get_raw_data_vlan()
    if raw:
        return bridge_vlan
    else:
        return _get_formatted_output_vlan(bridge_vlan)


def show_fdb(raw: bool, interface: str):
    fdb_data = _get_raw_data_fdb(interface)
    if raw:
        return fdb_data
    else:
        return _get_formatted_output_fdb(fdb_data)


def show_mdb(raw: bool, interface: str):
    mdb_data = _get_raw_data_mdb(interface)
    if raw:
        return mdb_data
    else:
        return _get_formatted_output_mdb(mdb_data)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
