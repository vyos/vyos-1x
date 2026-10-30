#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

import os
import re
import argparse

from vyos.utils.process import call
from vyos.utils.process import is_systemd_service_active

SWANCTL_CONF = '/etc/swanctl/swanctl.conf'
IPSEC_SERVICE = 'strongswan.service'


def get_peer_connections(peer, tunnel, return_all = False):
    search = rf'^[\s]*({peer}-(tunnel-[\d]+|vti))[\s]*{{'
    matches = []
    if not os.path.exists(SWANCTL_CONF):
        return matches
    with open(SWANCTL_CONF, 'r') as f:
        for line in f.readlines():
            result = re.match(search, line)
            if result:
                suffix = f'tunnel-{tunnel}' if tunnel.isnumeric() else tunnel
                if return_all or (result[2] == suffix):
                    matches.append(result[1])
    return matches


def show_status():
    if not is_systemd_service_active(IPSEC_SERVICE):
        print('IPsec process not running')
        return
    call('swanctl --stats')


def debug_peer(peer, tunnel):
    peer = peer.replace(':', '-')
    ipsec_running = is_systemd_service_active(IPSEC_SERVICE)
    if not peer or peer == "all":
        debug_commands = []
        if ipsec_running:
            debug_commands = [
                "swanctl --stats",
                "swanctl -L",
                "swanctl -l",
                "swanctl -P",
            ]
        else:
            print('IPsec process not running')
        debug_commands += [
            "ip x sa show",
            "ip x policy show",
            "ip tunnel show",
            "ip address",
            "ip rule show",
            "ip route | head -100",
            "ip route show table 220"
        ]
        for debug_cmd in debug_commands:
            # call() output bypasses our buffer, flush to keep the order
            print(f'\n### {debug_cmd} ###', flush=True)
            call(debug_cmd)
        return

    if not tunnel or tunnel == 'all':
        tunnel = ''

    conns = get_peer_connections(peer, tunnel, return_all = (tunnel == '' or tunnel == 'all'))

    if not conns:
        print('Peer not found, aborting')
        return

    if not ipsec_running:
        print('IPsec process not running')
        return

    call(f'swanctl --list-conns --ike {peer}')
    for conn in conns:
        call(f'swanctl --list-sas --ike {peer} --child {conn}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', help='Control action', required=True)
    parser.add_argument('--name', help='Name for peer reset', required=False)
    parser.add_argument('--tunnel', help='Specific tunnel of peer', required=False)

    args = parser.parse_args()


    if args.action == "vpn-debug":
        debug_peer(args.name, args.tunnel)
    elif args.action == "status":
        show_status()
