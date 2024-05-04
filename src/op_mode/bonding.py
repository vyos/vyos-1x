#!/usr/bin/env python3
#
# Copyright (C) 2016-2024 VyOS maintainers and contributors
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
#
# This script will parse 'sudo cat /proc/net/bonding/<interface name>' and return table output for lacp related info

import subprocess
import re
import sys
import typing
from tabulate import tabulate

import vyos.opmode
from vyos.configquery import ConfigTreeQuery

def list_to_dict(data, headers, basekey):
    data_list = {basekey: []}

    for row in data:
        row_dict = {headers[i]: row[i] for i in range(len(headers))}
        data_list[basekey].append(row_dict)

    return data_list

def show_lacp_neighbors(raw: bool, interface: typing.Optional[str]):
    headers = ["Interface", "Member", "Local ID", "Remote ID"]
    data = subprocess.run(f"cat /proc/net/bonding/{interface}", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True, text=False).stdout.decode('utf-8')
    if 'Bonding Mode: IEEE 802.3ad Dynamic link aggregation' not in data:
        raise vyos.opmode.DataUnavailable(f"{interface} is not present or not configured with mode 802.3ad")

    pattern = re.compile(
        r"Slave Interface: (?P<member>\w+\d+).*?"
        r"system mac address: (?P<local_id>[0-9a-f:]+).*?"
        r"details partner lacp pdu:.*?"
        r"system mac address: (?P<remote_id>[0-9a-f:]+)",
        re.DOTALL
    )

    interfaces = []

    for match in re.finditer(pattern, data):
        member = match.group("member")
        local_id = match.group("local_id")
        remote_id = match.group("remote_id")
        interfaces.append([interface, member, local_id, remote_id])

    if raw:
        return list_to_dict(interfaces, headers, 'lacp')
    else:
        return tabulate(interfaces, headers)

def show_lacp_detail(raw: bool, interface: typing.Optional[str]):
    headers = ["Interface", "Members", "Mode", "Rate", "System-MAC", "Hash"]
    query = ConfigTreeQuery()

    if interface:
        intList = [interface]
    else:
        intList = query.list_nodes(['interfaces', 'bonding'])

    bondList = []

    for interface in intList:
        data = subprocess.run(f"cat /proc/net/bonding/{interface}", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True, text=False).stdout.decode('utf-8')
        if 'Bonding Mode: IEEE 802.3ad Dynamic link aggregation' not in data:
            continue

        mode_active = "active" if "LACP active: on" in data else "passive"
        lacp_rate = re.search(r"LACP rate: (\w+)", data).group(1) if re.search(r"LACP rate: (\w+)", data) else "N/A"
        hash_policy = re.search(r"Transmit Hash Policy: (.+?) \(\d+\)", data).group(1) if re.search(r"Transmit Hash Policy: (.+?) \(\d+\)", data) else "N/A"
        system_mac = re.search(r"System MAC address: ([0-9a-f:]+)", data).group(1) if re.search(r"System MAC address: ([0-9a-f:]+)", data) else "N/A"
        if raw:
            members = re.findall(r"Slave Interface: ([a-zA-Z0-9:_-]+)", data)
        else:
            members = ",".join(set(re.findall(r"Slave Interface: ([a-zA-Z0-9:_-]+)", data)))

        bondList.append([interface, members, mode_active, lacp_rate, system_mac, hash_policy])

    if raw:
        return list_to_dict(bondList, headers, 'lacp')
    else:
        return tabulate(bondList, headers)

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
