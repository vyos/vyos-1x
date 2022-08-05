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

import re
import sys
from vyos.util import call
import vyos.opmode


SWANCTL_CONF = '/etc/swanctl/swanctl.conf'


def get_peer_connections(peer, tunnel, return_all = False):
    peer = peer.replace(':', '-')
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


def reset_peer(peer: str, tunnel:str):
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


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
