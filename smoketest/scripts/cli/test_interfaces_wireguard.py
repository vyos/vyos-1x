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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import unittest

from base_interfaces_test import BasicInterfaceTest
from vyos.configsession import ConfigSessionError
from vyos.utils.file import read_file
from vyos.utils.process import cmd
from vyos.utils.process import is_systemd_service_running

base_path = ['interfaces', 'wireguard']
domain_resolver = 'vyos-domain-resolver.service'
class WireGuardInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'wireguard']
        cls._options = {
            'wg0': ['private-key wBbGJJXYllwDcw63AFjiIR6ZlsvqvAf3eDwog64Dp0Q=',
                    'peer RED public-key 6hkkfxN4VUQLu36NLZr47I7ST/FkQl2clPWr+9a6ZH8=',
                    'peer RED allowed-ips 169.254.0.0/16',
                    'port 5678'],
            'wg1': ['private-key QFwnBHlHYspehvpklBKb7cikM+QMkEy2p6gfsg06S08=',
                    'peer BLUE public-key hRJLmP8SVU9/MLmPmYmpOa+RTB4F/zhDqA+/QDuW1Hg=',
                    'peer BLUE allowed-ips 169.254.0.0/16',
                    'port 4567'],
        }
        cls._interfaces = list(cls._options)

        super(WireGuardInterfaceTest, cls).setUpClass()

    def test_wireguard_peer(self):
        # Create WireGuard interfaces with associated peers
        for intf in self._interfaces:
            peer = 'foo-' + intf
            privkey = '6ISOkASm6VhHOOSz/5iIxw+Q9adq9zA17iMM4X40dlc='
            psk = 'u2xdA70hkz0S1CG0dZlOh0aq2orwFXRIVrKo4DCvHgM='
            pubkey = 'n6ZZL7ph/QJUJSUUTyu19c77my1dRCDHkMzFQUO9Z3A='

            for addr in self._test_addr:
                self.cli_set(base_path + [intf, 'address', addr])

            self.cli_set(base_path + [intf, 'private-key', privkey])

            self.cli_set(base_path + [intf, 'peer', peer, 'address', '127.0.0.1'])
            self.cli_set(base_path + [intf, 'peer', peer, 'port', '1337'])

            # Allow different prefixes to traverse the tunnel
            allowed_ips = ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']
            for ip in allowed_ips:
                self.cli_set(base_path + [intf, 'peer', peer, 'allowed-ips', ip])

            self.cli_set(base_path + [intf, 'peer', peer, 'preshared-key', psk])
            self.cli_set(base_path + [intf, 'peer', peer, 'public-key', pubkey])
            self.cli_commit()

            self.assertTrue(os.path.isdir(f'/sys/class/net/{intf}'))

    def test_wireguard_add_remove_peer(self):
        # T2939: Create WireGuard interfaces with associated peers.
        # Remove one of the configured peers.
        # T4774: Test prevention of duplicate peer public keys
        interface = 'wg0'
        port = '12345'
        privkey = '6ISOkASm6VhHOOSz/5iIxw+Q9adq9zA17iMM4X40dlc='
        pubkey_1 = 'n1CUsmR0M2LUUsyicBd6blZICwUqqWWHbu4ifZ2/9gk='
        pubkey_2 = 'ebFx/1G0ti8tvuZd94sEIosAZZIznX+dBAKG/8DFm0I='

        self.cli_set(base_path + [interface, 'address', '172.16.0.1/24'])
        self.cli_set(base_path + [interface, 'private-key', privkey])

        self.cli_set(base_path + [interface, 'peer', 'PEER01', 'public-key', pubkey_1])
        self.cli_set(base_path + [interface, 'peer', 'PEER01', 'port', port])
        self.cli_set(base_path + [interface, 'peer', 'PEER01', 'allowed-ips', '10.205.212.10/32'])
        self.cli_set(base_path + [interface, 'peer', 'PEER01', 'address', '192.0.2.1'])

        self.cli_set(base_path + [interface, 'peer', 'PEER02', 'public-key', pubkey_1])
        self.cli_set(base_path + [interface, 'peer', 'PEER02', 'port', port])
        self.cli_set(base_path + [interface, 'peer', 'PEER02', 'allowed-ips', '10.205.212.11/32'])
        self.cli_set(base_path + [interface, 'peer', 'PEER02', 'address', '192.0.2.2'])

        # Duplicate pubkey_1
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + [interface, 'peer', 'PEER02', 'public-key', pubkey_2])

        # Commit peers
        self.cli_commit()

        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface}'))

        # Delete second peer
        self.cli_delete(base_path + [interface, 'peer', 'PEER01'])
        self.cli_commit()

    def test_wireguard_same_public_key(self):
        # T5413: Test prevention of equality interface public key and peer's
        #        public key
        interface = 'wg0'
        port = '12345'
        privkey = 'OOjcXGfgQlAuM6q8Z9aAYduCua7pxf7UKYvIqoUPoGQ='
        pubkey_fail = 'eiVeYKq66mqKLbrZLzlckSP9voaw8jSFyVNiNTdZDjU='
        pubkey_ok = 'ebFx/1G0ti8tvuZd94sEIosAZZIznX+dBAKG/8DFm0I='

        self.cli_set(base_path + [interface, 'address', '172.16.0.1/24'])
        self.cli_set(base_path + [interface, 'private-key', privkey])

        self.cli_set(base_path + [interface, 'peer', 'PEER01', 'public-key', pubkey_fail])
        self.cli_set(base_path + [interface, 'peer', 'PEER01', 'allowed-ips', '10.205.212.10/32'])
        self.cli_set(base_path + [interface, 'peer', 'PEER01', 'address', '192.0.2.1'])

        # The same pubkey as the interface wg0
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + [interface, 'peer', 'PEER01', 'public-key', pubkey_ok])

        # If address is defined for a peer, so must be the peer port
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + [interface, 'peer', 'PEER01', 'port', port])

        # Commit peers
        self.cli_commit()

        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface}'))

    def test_wireguard_threaded(self):
        # T5409: Test adding threaded option on interface.
        for intf in self._interfaces:
            for option in self._options.get(intf, []):
                self.cli_set(self._base_path + [intf] + option.split())

            self.cli_set(base_path + [intf, 'per-client-thread'])

        # Commit peers
        self.cli_commit()

        for intf in self._interfaces:
            tmp = read_file(f'/sys/class/net/{intf}/threaded')
            self.assertTrue(tmp, "1")

    def test_wireguard_peer_change(self):
        # T5707 changing WireGuard CLI public key of a peer - it's not removed
        # Also check if allowed-ips update

        def get_peers(interface) -> list[tuple]:
            tmp = cmd(f'sudo wg show {interface} dump')
            first_line = True
            peers = []
            allowed_ips = []
            for line in tmp.split('\n'):
                if not line:
                    continue # Skip empty lines and last line
                items = line.split('\t')
                if first_line:
                    self.assertEqual(privkey, items[0])
                    first_line = False
                else:
                    peers.append(items[0])
                    allowed_ips.append(items[3])
            return peers, allowed_ips

        interface = 'wg1337'
        port = '1337'
        privkey = 'iJi4lb2HhkLx2KSAGOjji2alKkYsJjSPkHkrcpxgEVU='
        pubkey_1 = 'srQ8VF6z/LDjKCzpxBzFpmaNUOeuHYzIfc2dcmoc/h4='
        pubkey_2 = '8pbMHiQ7NECVP7F65Mb2W8+4ldGG2oaGvDSpSEsOBn8='
        allowed_ips_1 = '10.205.212.10/32'
        allowed_ips_2 = '10.205.212.11/32'

        self.cli_set(base_path + [interface, 'address', '172.16.0.1/24'])
        self.cli_set(base_path + [interface, 'port', port])
        self.cli_set(base_path + [interface, 'private-key', privkey])

        self.cli_set(base_path + [interface, 'peer', 'VyOS', 'public-key', pubkey_1])
        self.cli_set(base_path + [interface, 'peer', 'VyOS', 'allowed-ips', allowed_ips_1])

        self.cli_commit()

        peers, _ = get_peers(interface)
        self.assertIn(pubkey_1, peers)
        self.assertNotIn(pubkey_2, peers)

        # Now change the public key of our peer
        self.cli_set(base_path + [interface, 'peer', 'VyOS', 'public-key', pubkey_2])
        self.cli_commit()

        # Verify config
        peers, _ = get_peers(interface)
        self.assertNotIn(pubkey_1, peers)
        self.assertIn(pubkey_2, peers)

        # Update allowed-ips
        self.cli_delete(base_path + [interface, 'peer', 'VyOS', 'allowed-ips', allowed_ips_1])
        self.cli_set(base_path + [interface, 'peer', 'VyOS', 'allowed-ips', allowed_ips_2])
        self.cli_commit()

        # Verify config
        _, allowed_ips = get_peers(interface)
        self.assertNotIn(allowed_ips_1, allowed_ips)
        self.assertIn(allowed_ips_2, allowed_ips)

    def test_wireguard_hostname(self):
        # T4930: Test dynamic endpoint support
        interface = 'wg1234'
        port = '54321'
        privkey = 'UOWIeZKNzijhgu0bPRy2PB3gnuOBLfQax5GiYfkmU3A='
        pubkey = '4nG5NfhHBQUq/DnwT0RjRoBCqAh3VrRHqdQgzC/xujk='

        base_interface_path = base_path + [interface]
        self.cli_set(base_interface_path + ['address', '172.16.0.1/24'])
        self.cli_set(base_interface_path + ['private-key', privkey])

        peer_base_path = base_interface_path + ['peer', 'dynamic01']
        self.cli_set(peer_base_path + ['port', port])
        self.cli_set(peer_base_path + ['public-key', pubkey])
        self.cli_set(peer_base_path + ['allowed-ips', '169.254.0.0/16'])
        self.cli_set(peer_base_path + ['address', '192.0.2.1'])
        self.cli_set(peer_base_path + ['host-name', 'wg.vyos.net'])

        # Peer address and host-name are mutually exclusive
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(peer_base_path + ['address'])

        # Commit peers
        self.cli_commit()

        # Ensure the service is running which checks for DNS changes
        self.assertTrue(is_systemd_service_running(domain_resolver))

        self.cli_delete(base_interface_path)
        self.cli_commit()

        # Ensure the service is no longer running after WireGuard interface is deleted
        self.assertFalse(is_systemd_service_running(domain_resolver))

if __name__ == '__main__':
    unittest.main(verbosity=2)
