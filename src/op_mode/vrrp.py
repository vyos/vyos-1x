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

import sys
import time
import argparse
import json
import tabulate

import vyos.keepalived
import vyos.util

config_dict_path = '/run/keepalived_config.dict'


# get disabled instances from a config
def vrrp_get_disabled():
    # read the dictionary file with configuration
    with open(config_dict_path, 'r') as dict_file:
        vrrp_config_dict = json.load(dict_file)
    vrrp_disabled = []
    # add disabled groups to the list
    for vrrp_group in vrrp_config_dict['vrrp_groups']:
        if vrrp_group['disable']:
            vrrp_disabled.append([vrrp_group['name'], vrrp_group['interface'], vrrp_group['vrid'], 'DISABLED', ''])
    # return list with disabled instances
    return vrrp_disabled


def print_summary():
    try:
        vyos.keepalived.force_json_dump()
        # Wait for keepalived to produce the data
        # Replace with inotify or similar if it proves problematic
        time.sleep(0.2)
        json_data = vyos.keepalived.get_json_data()
        vyos.keepalived.remove_vrrp_data("json")
    except:
        print("VRRP information is not available")
        sys.exit(1)

    groups = []
    for group in json_data:
        data = group["data"]

        name = data["iname"]

        ltrans_timestamp = float(data["last_transition"])
        ltrans_time = vyos.util.seconds_to_human(int(time.time() - ltrans_timestamp))

        interface = data["ifp_ifname"]
        vrid = data["vrid"]

        state = vyos.keepalived.decode_state(data["state"])

        row = [name, interface, vrid, state, ltrans_time]
        groups.append(row)

    # add to the active list disabled instances
    groups.extend(vrrp_get_disabled())
    headers = ["Name", "Interface", "VRID", "State", "Last Transition"]
    output = tabulate.tabulate(groups, headers)
    print(output)


def print_statistics():
    try:
        vyos.keepalived.force_stats_dump()
        time.sleep(0.2)
        output = vyos.keepalived.get_statistics()
        print(output)
        vyos.keepalived.remove_vrrp_data("stats")
    except:
        print("VRRP statistics are not available")
        sys.exit(1)


def print_state_data():
    try:
        vyos.keepalived.force_state_data_dump()
        time.sleep(0.2)
        output = vyos.keepalived.get_state_data()
        print(output)
        vyos.keepalived.remove_vrrp_data("state")
    except:
        print("VRRP information is not available")
        sys.exit(1)


parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("-s", "--summary", action="store_true", help="Print VRRP summary")
group.add_argument("-t", "--statistics", action="store_true", help="Print VRRP statistics")
group.add_argument("-d", "--data", action="store_true", help="Print detailed VRRP data")

args = parser.parse_args()

# Exit early if VRRP is dead or not configured
if not vyos.keepalived.vrrp_running():
    print("VRRP is not running")
    sys.exit(0)

if args.summary:
    print_summary()
elif args.statistics:
    print_statistics()
elif args.data:
    print_state_data()
else:
    parser.print_help()
    sys.exit(1)
