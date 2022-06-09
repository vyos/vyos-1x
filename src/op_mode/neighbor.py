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
import typing

import opmode


def get_raw_data(family, interface=None, state=None):
    from json import loads
    from vyos.util import cmd

    if interface:
        interface = f"dev {interface}"
    else:
        interface = ""

    if state:
        state = f"nud {state}"
    else:
        state = ""

    neigh_cmd = f"ip --family {family} --json neighbor list {interface} {state}"

    data = loads(cmd(neigh_cmd))

    return data

def format_neighbors(neighs, interface=None):
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
        elif interface:
            dev = interface
        else:
            raise ValueError("interface is not defined")

        return [dst, dev, lladdr, state]

    neighs = map(entry_to_list, neighs)

    headers = ["Address", "Interface", "Link layer address",  "State"]
    return tabulate(neighs, headers)

def show(raw: bool, family: str, interface: typing.Optional[str], state: typing.Optional[str]):
    """ Display neighbor table contents """
    data = get_raw_data(family, interface, state=state)

    if raw:
        return data
    else:
        return format_neighbors(data, interface)


if __name__ == '__main__':
    from argparse import ArgumentParser

    try:
        print(opmode.run(sys.modules[__name__]))
    except ValueError as e:
        print(e)
        sys.exit(1)

