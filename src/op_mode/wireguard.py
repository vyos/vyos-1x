#!/usr/bin/env python3
#
# Copyright (C) 2018-2021 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import sys
import tabulate

from vyos.config import Config
from vyos.ifconfig import WireGuardIf
from vyos.util import cmd
from vyos import ConfigError

base = ['interfaces', 'wireguard']

def get_public_keys():
    config = Config()
    headers = ['Interface', 'Peer', 'Public Key']
    out = []
    if config.exists(base):
        wg_interfaces = config.get_config_dict(base, key_mangling=('-', '_'),
                                             get_first_key=True,
                                             no_tag_node_value_mangle=True)

        for wg, wg_conf in wg_interfaces.items():
            if 'peer' in wg_conf:
                for peer, peer_conf in wg_conf['peer'].items():
                    out.append([wg, peer, peer_conf['public_key']])

    print("Wireguard Public Keys:")
    print(tabulate.tabulate(out, headers))

def get_private_keys():
    config = Config()
    headers = ['Interface', 'Private Key', 'Public Key']
    out = []
    if config.exists(base):
        wg_interfaces = config.get_config_dict(base, key_mangling=('-', '_'),
                                             get_first_key=True,
                                             no_tag_node_value_mangle=True)

        for wg, wg_conf in wg_interfaces.items():
            private_key = wg_conf['private_key']
            public_key = cmd('wg pubkey', input=private_key)
            out.append([wg, private_key, public_key])

    print("Wireguard Private Keys:")
    print(tabulate.tabulate(out, headers))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='wireguard key management')
    parser.add_argument(
        '--showpub', action="store_true", help='shows public keys')
    parser.add_argument(
        '--showpriv', action="store_true", help='shows private keys')
    parser.add_argument(
        '--showinterface', action="store", help='shows interface details')
    args = parser.parse_args()

    try:
        if args.showpub:
            get_public_keys()
        if args.showpriv:
            get_private_keys()
        if args.showinterface:
            try:
                intf = WireGuardIf(args.showinterface, create=False, debug=False)
                print(intf.operational.show_interface())
            # the interface does not exists
            except Exception:
                pass

    except ConfigError as e:
        print(e)
        sys.exit(1)
