#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
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

import json
import argparse
import ipaddress

import tabulate

import vyos.config

from isc_dhcp_leases import Lease, IscDhcpLeases


lease_file = "/config/dhcpdv6.leases"

def get_lease_data(lease):
    data = {}

    # End time may not be present in backup leases
    try:
        data["expires"] = lease.end.strftime("%Y/%m/%d %H:%M:%S")
    except:
        data["expires"] = ""

    data["duid"] = lease.host_identifier_string
    data["ip"] = lease.ip

    return data

def get_leases(leases, state=None):
    leases = IscDhcpLeases(lease_file).get()

    if state is not None:
        leases = list(filter(lambda x: x.binding_state == 'active', leases))

    return list(map(get_lease_data, leases))

def show_leases(leases):
    headers = ["IPv6 address", "Lease expiration", "DUID"]

    lease_list = []
    for l in leases:
        lease_list.append([l["ip"], l["expires"], l["duid"]])

    output = tabulate.tabulate(lease_list, headers)

    print(output)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-l", "--leases", action="store_true", help="Show DHCP leases")
    group.add_argument("-s", "--statistics", action="store_true", help="Show DHCP statistics")

    parser.add_argument("-p", "--pool", type=str, action="store", help="Show lease for specific pool")
    parser.add_argument("-j", "--json", action="store_true", default=False, help="Product JSON output")

    args = parser.parse_args()

    if args.leases:
        leases = get_leases(lease_file, state='active')
        show_leases(leases)
    elif args.statistics:
        print("DHCPv6 statistics option is not available")
    else:
        print("Invalid option")
