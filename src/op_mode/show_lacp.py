#!/usr/bin/env python3
#
# Copyright (C) 2016-2022 VyOS maintainers and contributors
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

from tabulate import tabulate
import subprocess
import re
import argparse

def get_all_bonds():
    return subprocess.run(f"cli-shell-api listActiveNodes interfaces bonding", stdout=subprocess.PIPE, shell=True, text=True).stdout.encode('utf-8').decode('utf-8')

def get_lacp_neighbors(interface):
    headers = ["Interface", "Member", "Local ID", "Remote ID"]
    data = subprocess.run(f"sudo cat /proc/net/bonding/{interface}", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True, text=False).stdout.decode('utf-8')
    if 'Bonding Mode: IEEE 802.3ad Dynamic link aggregation' not in data:
        exit("Bond is not configured with mode 802.3ad")

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

    if interfaces:
        print(tabulate(interfaces, headers))
    else:
        print("No Member interfaces found!")

def get_bond_info(interface):
    headers = ["Interface", "Members", "Mode", "Rate", "System MAC", "Hash"]
    data = subprocess.run(f"sudo cat /proc/net/bonding/{interface}", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True, text=False).stdout.decode('utf-8')
    if 'Bonding Mode: IEEE 802.3ad Dynamic link aggregation' not in data:
        if args.detailall:
            return None, headers
        else:
            exit("Bond is not configured with mode 802.3ad")

    mode_active = "active" if "LACP active: on" in data else "passive"
    lacp_rate = re.search(r"LACP rate: (\w+)", data).group(1) if re.search(r"LACP rate: (\w+)", data) else "N/A"
    hash_policy = re.search(r"Transmit Hash Policy: (.+?) \(\d+\)", data).group(1) if re.search(r"Transmit Hash Policy: (.+?) \(\d+\)", data) else "N/A"
    system_mac = re.search(r"System MAC address: ([0-9a-f:]+)", data).group(1) if re.search(r"System MAC address: ([0-9a-f:]+)", data) else "N/A"

    members = ",".join(set(re.findall(r"Slave Interface: ([a-zA-Z0-9:_-]+)", data)))

    table_data = []

    table_data = [interface, members, mode_active, lacp_rate, system_mac, hash_policy]

    if table_data:
        return table_data, headers
    else:
        print("No member interfaces found!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--interface', help='Bond Interface', required=False)
    parser.add_argument('--detail', help='LACP Details', required=False)
    parser.add_argument('--detailall', help='LACP Details', required=False)

    args = parser.parse_args()

    if args.detail:
        data, headers = get_bond_info(args.interface)
        print(tabulate([data], headers))
    elif args.detailall:
        bondList = []
        intList = get_all_bonds().split()
        if intList:
            for i in intList:
                data, headers = get_bond_info(i.replace("'", ""))
                if data:
                    bondList.append(data)
            print(tabulate(bondList, headers))
        else:
            exit("No bond interfaces found")
    else:
        get_lacp_neighbors(args.interface)
