#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

import os
import unittest

from vyos.configsession import ConfigSession, ConfigSessionError
from base_interfaces_test import BasicInterfaceTest

# Generate WireGuard default keypair
if not os.path.isdir('/config/auth/wireguard/default'):
    os.system('sudo /usr/libexec/vyos/op_mode/wireguard.py --genkey')

base_path = ['interfaces', 'wireguard']

class WireGuardInterfaceTest(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        self._test_addr = ['192.0.2.1/26', '192.0.2.255/31', '192.0.2.64/32',
                          '2001:db8:1::ffff/64', '2001:db8:101::1/112']
        self._interfaces = ['wg0', 'wg1']

    def tearDown(self):
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_peer(self):
        """ Create WireGuard interfaces with associated peers """
        for intf in self._interfaces:
            peer = 'foo-' + intf
            psk = 'u2xdA70hkz0S1CG0dZlOh0aq2orwFXRIVrKo4DCvHgM='
            pubkey = 'n6ZZL7ph/QJUJSUUTyu19c77my1dRCDHkMzFQUO9Z3A='

            for addr in self._test_addr:
                self.session.set(base_path + [intf, 'address', addr])

            self.session.set(base_path + [intf, 'peer', peer, 'address', '127.0.0.1'])
            self.session.set(base_path + [intf, 'peer', peer, 'port', '1337'])

            # Allow different prefixes to traverse the tunnel
            allowed_ips = ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']
            for ip in allowed_ips:
                self.session.set(base_path + [intf, 'peer', peer, 'allowed-ips', ip])

            self.session.set(base_path + [intf, 'peer', peer, 'preshared-key', psk])
            self.session.set(base_path + [intf, 'peer', peer, 'pubkey', pubkey])
            self.session.commit()

            self.assertTrue(os.path.isdir(f'/sys/class/net/{intf}'))


    def test_add_remove_peer(self):
        """ Create WireGuard interfaces with associated peers. Remove one of
        the configured peers. Bug reported as T2939 """
        interface = 'wg0'
        port = '12345'
        pubkey_1 = 'n1CUsmR0M2LUUsyicBd6blZICwUqqWWHbu4ifZ2/9gk='
        pubkey_2 = 'ebFx/1G0ti8tvuZd94sEIosAZZIznX+dBAKG/8DFm0I='

        self.session.set(base_path + [interface, 'address', '172.16.0.1/24'])

        self.session.set(base_path + [interface, 'peer', 'PEER01', 'pubkey', pubkey_1])
        self.session.set(base_path + [interface, 'peer', 'PEER01', 'port', port])
        self.session.set(base_path + [interface, 'peer', 'PEER01', 'allowed-ips', '10.205.212.10/32'])
        self.session.set(base_path + [interface, 'peer', 'PEER01', 'address', '192.0.2.1'])

        self.session.set(base_path + [interface, 'peer', 'PEER02', 'pubkey', pubkey_2])
        self.session.set(base_path + [interface, 'peer', 'PEER02', 'port', port])
        self.session.set(base_path + [interface, 'peer', 'PEER02', 'allowed-ips', '10.205.212.11/32'])
        self.session.set(base_path + [interface, 'peer', 'PEER02', 'address', '192.0.2.2'])

        # Commit peers
        self.session.commit()

        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface}'))

        # Delete second peer
        self.session.delete(base_path + [interface, 'peer', 'PEER01'])
        self.session.commit()



if __name__ == '__main__':
    unittest.main()
