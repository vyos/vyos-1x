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
from subprocess import TimeoutExpired

from vyos.util import call

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

def reset_peer(peer, tunnel):
    if not peer:
        print('Invalid peer, aborting')
        return

    conns = get_peer_connections(peer, tunnel, return_all = (not tunnel or tunnel == 'all'))

    if not conns:
        print('Tunnel(s) not found, aborting')
        return

    result = True
    for conn in conns:
        try:
            call(f'sudo /usr/sbin/ipsec down {conn}{{*}}', timeout = 10)
            call(f'sudo /usr/sbin/ipsec up {conn}', timeout = 10)
        except TimeoutExpired as e:
            print(f'Timed out while resetting {conn}')
            result = False


    print('Peer reset result: ' + ('success' if result else 'failed'))

def get_profile_connection(profile, tunnel = None):
    search = rf'(dmvpn-{profile}-[\w]+)' if tunnel == 'all' else rf'(dmvpn-{profile}-{tunnel})'
    with open(SWANCTL_CONF, 'r') as f:
        for line in f.readlines():
            result = re.search(search, line)
            if result:
                return result[1]
    return None

def reset_profile(profile, tunnel):
    if not profile:
        print('Invalid profile, aborting')
        return

    if not tunnel:
        print('Invalid tunnel, aborting')
        return

    conn = get_profile_connection(profile)

    if not conn:
        print('Profile not found, aborting')
        return

    call(f'sudo /usr/sbin/ipsec down {conn}')
    result = call(f'sudo /usr/sbin/ipsec up {conn}')

    print('Profile reset result: ' + ('success' if result == 0 else 'failed'))

def debug_peer(peer, tunnel):
    peer = peer.replace(':', '-')
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

    if not tunnel or tunnel == 'all':
        tunnel = ''

    conns = get_peer_connections(peer, tunnel, return_all = (tunnel == '' or tunnel == 'all'))

    if not conns:
        print('Peer not found, aborting')
        return

    for conn in conns:
        call(f'sudo /usr/sbin/ipsec statusall | grep {conn}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', help='Control action', required=True)
    parser.add_argument('--name', help='Name for peer reset', required=False)
    parser.add_argument('--tunnel', help='Specific tunnel of peer', required=False)

    args = parser.parse_args()

    if args.action == 'reset-peer':
        reset_peer(args.name, args.tunnel)
    elif args.action == "reset-profile":
        reset_profile(args.name, args.tunnel)
    elif args.action == "vpn-debug":
        debug_peer(args.name, args.tunnel)
