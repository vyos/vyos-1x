#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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
import sys
import vici

from vyos.utils.process import process_named_running

ike_sa_peer_prefix = """\
Peer ID / IP                            Local ID / IP
------------                            -------------"""

ike_sa_tunnel_prefix = """

    State  IKEVer  Encrypt      Hash          D-H Group      NAT-T  A-Time  L-Time
    -----  ------  -------      ----          ---------      -----  ------  ------"""

def s(byte_string):
    return str(byte_string, 'utf-8')

def ike_sa(peer, nat):
    session = vici.Session()
    sas = session.list_sas()
    peers = []
    for conn in sas:
        for name, sa in conn.items():
            if name.startswith('peer_') and name in peers:
                continue
            if nat and 'nat-local' not in sa:
                continue
            peers.append(name)
            remote_str = f'{s(sa["remote-host"])} {s(sa["remote-id"])}' if s(sa['remote-id']) != '%any' else s(sa["remote-host"])
            local_str = f'{s(sa["local-host"])} {s(sa["local-id"])}' if s(sa['local-id']) != '%any' else s(sa["local-host"])
            print(ike_sa_peer_prefix)
            print('%-39s %-39s' % (remote_str, local_str))
            state = 'up' if 'state' in sa and s(sa['state']) == 'ESTABLISHED' else 'down'
            version = 'IKEv' + s(sa['version'])
            encryption = f'{s(sa["encr-alg"])}' if 'encr-alg' in sa else 'n/a'
            if 'encr-keysize' in sa:
                encryption += '_' + s(sa["encr-keysize"])
            integrity = s(sa['integ-alg']) if 'integ-alg' in sa else 'n/a'
            dh_group = s(sa['dh-group']) if 'dh-group' in sa else 'n/a'
            natt = 'yes' if 'nat-local' in sa and s(sa['nat-local']) == 'yes' else 'no'
            atime = s(sa['established']) if 'established' in sa else '0'
            ltime = s(sa['rekey-time']) if 'rekey-time' in sa else '0'
            print(ike_sa_tunnel_prefix)
            print('    %-6s %-6s  %-12s %-13s %-14s %-6s %-7s %-7s\n' % (state, version, encryption, integrity, dh_group, natt, atime, ltime))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--peer', help='Peer name', required=False)
    parser.add_argument('--nat', help='NAT Traversal', required=False)

    args = parser.parse_args()

    if not process_named_running('charon-systemd'):
        print("IPsec Process NOT Running")
        sys.exit(0)

    ike_sa(args.peer, args.nat)
