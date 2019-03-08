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
import sys

from vyos.config import Config
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

def get_pool_size(config, pool):
    size = 0
    subnets = config.list_effective_nodes("service dhcp-server shared-network-name {0} subnet".format(pool))
    for s in subnets:
        ranges = config.list_effective_nodes("service dhcp-server shared-network-name {0} subnet {1} range".format(pool, s))
        for r in ranges:
            start = config.return_effective_value("service dhcp-server shared-network-name {0} subnet {1} range {2} start".format(pool, s, r))
            stop = config.return_effective_value("service dhcp-server shared-network-name {0} subnet {1} range {2} stop".format(pool, s, r))

            size += int(ipaddress.IPv4Address(stop)) - int(ipaddress.IPv4Address(start))

    return size

def show_pool_stats(stats):
    headers = ["Pool", "Size", "Leases", "Available", "Usage"]
    output = tabulate.tabulate(stats, headers)

    print(output)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-l", "--leases", action="store_true", help="Show DHCP leases")
    group.add_argument("-s", "--statistics", action="store_true", help="Show DHCP statistics")

    parser.add_argument("-e", "--expired", action="store_true", help="Show expired leases")
    parser.add_argument("-p", "--pool", type=str, action="store", help="Show lease for specific pool")
    parser.add_argument("-j", "--json", action="store_true", default=False, help="Product JSON output")

    args = parser.parse_args()

    # Do nothing if service is not configured
    config = Config()
    if not config.exists_effective('service dhcp-server'):
        print("DHCP service is not configured")
        sys.exit(0)

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

        if args.json:
            print(json.dumps(leases, indent=4))
        else:
            show_leases(leases)
    elif args.statistics:
        pools = []

        # Get relevant pools
        if args.pool:
            pools = [args.pool]
        else:
            pools = config.list_effective_nodes("service dhcp-server shared-network-name")

        # Get pool usage stats
        stats = []
        for p in pools:
            size = get_pool_size(config, p)
            leases = len(get_leases(lease_file, state='active', pool=args.pool))

            if size != 0:
                use_percentage = round(leases / size) * 100
            else:
                use_percentage = 0

            if args.json:
                pool_stats = {"pool": p, "size": size, "leases": leases,
                              "available": (size - leases), "percentage": use_percentage}
            else:
                # For tabulate
                pool_stats = [p, size, leases, size - leases, "{0}%".format(use_percentage)]
            stats.append(pool_stats)

        # Print stats
        if args.json:
            print(json.dumps(stats, indent=4))
        else:
            show_pool_stats(stats)
    else:
        print("Use either --leases or --statistics option")
