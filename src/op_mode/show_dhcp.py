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

import argparse

import tabulate

import vyos.config

from isc_dhcp_leases import Lease, IscDhcpLeases


lease_file = "/config/dhcpd.leases"
pool_key = "shared-networkname"

def in_pool(lease, pool):
    if pool_key in lease.sets:
        if lease.sets[pool_key] == pool:
            return True

    return False

def get_lease_data(lease):
    data = {}

    # End time may not be present in backup leases
    try:
        data["expires"] = lease.end.strftime("%Y/%m/%d %H:%M:%S")
    except:
        data["expires"] = ""

    data["hardware_address"] = lease.ethernet
    data["hostname"] = lease.hostname
    data["ip"] = lease.ip

    try:
        data["pool"] = lease.sets[pool_key]
    except:
        data["pool"] = ""

    return data

def get_leases(leases, state=None, pool=None):
    leases = IscDhcpLeases(lease_file).get()

    if state is not None:
        leases = list(filter(lambda x: x.binding_state == 'active', leases))

    if pool is not None:
        leases = list(filter(lambda x: in_pool(x, pool), leases))

    return list(map(get_lease_data, leases))

def show_leases(leases):
    headers = ["IP address", "Hardware address", "Lease expiration", "Pool", "Client Name"]

    lease_list = []
    for l in leases:
        lease_list.append([l["ip"], l["hardware_address"], l["expires"], l["pool"], l["hostname"]])

    output = tabulate.tabulate(lease_list, headers)
    
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-l", "--leases", action="store_true", help="Show DHCP leases")
    group.add_argument("-s", "--statistics", action="store_true", help="Show DHCP statistics")

    parser.add_argument("-e", "--expired", action="store_true", help="Show expired leases")
    parser.add_argument("-p", "--pool", type=str, action="store", help="Show lease for specific pool")

    args = parser.parse_args()

    if args.leases:
        if args.expired:
            if args.pool:
                leases = get_leases(lease_file, state='free', pool=args.pool)
            else:
                leases = get_leases(lease_file, state='free')
        else:
            if args.pool:
                leases = get_leases(lease_file, state='active', pool=args.pool)
            else:
                leases = get_leases(lease_file, state='active')

        show_leases(leases)
