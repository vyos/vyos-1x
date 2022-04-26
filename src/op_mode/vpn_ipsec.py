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

import argparse

from vyos.util import call


def debug_peer(peer, tunnel):
    if not peer or peer == "all":
        debug_commands = [
            "sudo ipsec statusall",
            "sudo swanctl -L",
            "sudo swanctl -l",
            "sudo swanctl -P",
            "sudo ip x sa show",
            "sudo ip x policy show",
            "sudo ip tunnel show",
            "sudo ip address",
            "sudo ip rule show",
            "sudo ip route | head -100",
            "sudo ip route show table 220"
        ]
        for debug_cmd in debug_commands:
            print(f'\n### {debug_cmd} ###')
            call(debug_cmd)
        return


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', help='Control action', required=True)
    parser.add_argument('--name', help='Name for peer reset', required=False)
    parser.add_argument('--tunnel', help='Specific tunnel of peer', required=False)

    args = parser.parse_args()

    if args.action == "vpn-debug":
        debug_peer(args.name, args.tunnel)
