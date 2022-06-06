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

# Sample output of `ip --json neigh list`:
#
# [
#   {
#     "dst": "192.168.1.1",
#     "dev": "eth0",                 # Missing if `dev ...` option is used
#     "lladdr": "00:aa:bb:cc:dd:ee", # May be missing for failed entries
#     "state": [
#       "REACHABLE"
#     ]
#  },
# ]

import sys


def get_raw_data(family, device=None, state=None):
    from json import loads
    from vyos.util import cmd

    if device:
        device = f"dev {device}"
    else:
        device = ""

    if state:
        state = f"nud {state}"
    else:
        state = ""

    neigh_cmd = f"ip --family {family} --json neighbor list {device} {state}"

    data = loads(cmd(neigh_cmd))

    return data

def get_formatted_output(family, device=None, state=None):
    from tabulate import tabulate

    def entry_to_list(e, intf=None):
        dst = e["dst"]

        # State is always a list in the iproute2 output
        state = ", ".join(e["state"])

        # Link layer address is absent from e.g. FAILED entries
        if "lladdr" in e:
            lladdr = e["lladdr"]
        else:
            lladdr = None

        # Device field is absent from outputs of `ip neigh list dev ...`
        if "dev" in e:
            dev = e["dev"]
        elif device:
            dev = device
        else:
            raise ValueError("interface is not defined")

        return [dst, dev, lladdr, state]

    neighs = get_raw_data(family, device=device, state=state)
    neighs = map(entry_to_list, neighs)

    headers = ["Address", "Interface", "Link layer address",  "State"]
    return tabulate(neighs, headers)

if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("-f", "--family", type=str, default="inet", help="Address family")
    parser.add_argument("-i", "--interface", type=str, help="Network interface")
    parser.add_argument("-s", "--state", type=str, help="Neighbor table entry state")

    args = parser.parse_args()

    if args.state:
        if args.state not in ["reachable", "failed", "stale", "permanent"]:
            raise ValueError(f"""Incorrect state "{args.state}"! Must be one of: reachable, stale, failed, permanent""")

    try:
        print(get_formatted_output(args.family, device=args.interface, state=args.state))
    except ValueError as e:
        print(e)
        sys.exit(1)
