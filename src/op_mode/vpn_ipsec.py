#!/usr/bin/env python3
#
# Copyright (C) 2021-2022 VyOS maintainers and contributors
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

import re
import argparse

from vyos.utils.process import call

SWANCTL_CONF = '/etc/swanctl/swanctl.conf'


def get_peer_connections(peer, tunnel, return_all = False):
    search = rf'^[\s]*(peer_{peer}_(tunnel_[\d]+|vti)).*'
    matches = []
    with open(SWANCTL_CONF, 'r') as f:
        for line in f.readlines():
            result = re.match(search, line)
            if result:
                suffix = f'tunnel_{tunnel}' if tunnel.isnumeric() else tunnel
                if return_all or (result[2] == suffix):
                    matches.append(result[1])
    return matches


def debug_peer(peer, tunnel):
    peer = peer.replace(':', '-')
    if not peer or peer == "all":
        debug_commands = [
            "ipsec statusall",
            "swanctl -L",
            "swanctl -l",
            "swanctl -P",
            "ip x sa show",
            "ip x policy show",
            "ip tunnel show",
            "ip address",
            "ip rule show",
            "ip route | head -100",
            "ip route show table 220"
        ]
        for debug_cmd in debug_commands:
            print(f'\n### {debug_cmd} ###')
            call(debug_cmd)
        return

    if not tunnel or tunnel == 'all':
        tunnel = ''

    conns = get_peer_connections(peer, tunnel, return_all = (tunnel == '' or tunnel == 'all'))

    if not conns:
        print('Peer not found, aborting')
        return

    for conn in conns:
        call(f'/usr/sbin/ipsec statusall | grep {conn}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', help='Control action', required=True)
    parser.add_argument('--name', help='Name for peer reset', required=False)
    parser.add_argument('--tunnel', help='Specific tunnel of peer', required=False)

    args = parser.parse_args()


    if args.action == "vpn-debug":
        debug_peer(args.name, args.tunnel)
