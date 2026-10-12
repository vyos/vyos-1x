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
from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.configsession import ConfigSessionError
from vyos.utils.process import cmdl

from vyos.ifconfig import Section

class PEthInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'pseudo-ethernet']

        cls._options = {}
        # we need to filter out VLAN interfaces identified by a dot (.)
        # in their name - just in case!
        if 'TEST_ETH' in os.environ:
            for tmp in os.environ['TEST_ETH'].split():
                cls._options.update({f'p{tmp}' : [f'source-interface {tmp}']})

        else:
            for tmp in Section.interfaces('ethernet'):
                if '.' in tmp:
                    continue
                cls._options.update({f'p{tmp}' : [f'source-interface {tmp}']})

        cls._interfaces = list(cls._options)
        # call base-classes classmethod
        super(PEthInterfaceTest, cls).setUpClass()

    def test_anycast_gateway(self):
        # Create the underlying bridge and sub-interface in the test

        for i, peth in enumerate(self._interfaces):
            eth = peth[1:]  # Convert peth0 -> eth0
            br = f'br{i}'
            vlan = str(i + 100)

            # Format the MAC using index as a two-digit hexadecimal
            mac_address = f'00:aa:aa:aa:aa:{i:02x}'

            with self.subTest(peth=peth, eth=eth, mac_address=mac_address, i=i):
                base_bridge_path = ['interfaces', 'bridge', br]
                base_br_member_path = base_bridge_path + ['member', 'interface']

                self.cli_set(base_bridge_path + ['enable-vlan'])
                self.cli_set(base_br_member_path + [eth, 'native-vlan', vlan])
                self.cli_set(base_br_member_path + [f'vxlan{i}'])
                self.cli_set(base_bridge_path + ['vif', vlan])

                self.cli_set(
                    self._base_path + [peth, 'source-interface', f'{br}.{vlan}']
                )
                self.cli_set(self._base_path + [peth, 'anycast-gateway'])

                # Anycast gateway requires MAC
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()

                self.cli_set(self._base_path + [peth, 'mac', mac_address])
                self.cli_commit()

                # Verify FDB entry exists with flag
                fdb = cmdl(['bridge', 'fdb', 'show', 'dev', br])
                self.assertIn(f'{mac_address} vlan {vlan} master {br} permanent', fdb)

                # Then remove just the anycast-gateway flag
                self.cli_delete(self._base_path + [peth, 'anycast-gateway'])
                self.cli_commit()

                fdb = cmdl(['bridge', 'fdb', 'show', 'dev', br])
                self.assertNotIn(f'{mac_address} vlan {vlan} master {br} permanent', fdb)

                # Clean up temp bridge and peth
                self.cli_delete(self._base_path + [peth])
                self.cli_delete(base_bridge_path)
                self.cli_commit()

    def test_anycast_gateway_shared_mac(self):
        # EVPN anycast gateway: same MAC on several VLANs of one bridge
        if not self._interfaces:
            self.skipTest('No Ethernet interface available')

        br = 'br0'
        eth = self._interfaces[0][1:]
        mac_address = '00:aa:aa:aa:aa:aa'
        vlans = ['200', '201', '202']
        base_bridge_path = ['interfaces', 'bridge', br]

        self.cli_set(base_bridge_path + ['enable-vlan'])
        self.cli_set(base_bridge_path + ['member', 'interface', eth, 'allowed-vlan', '200-202'])
        for vlan in vlans:
            self.cli_set(base_bridge_path + ['vif', vlan])
            peth = f'peth{vlan}'
            self.cli_set(self._base_path + [peth, 'source-interface', f'{br}.{vlan}'])
            self.cli_set(self._base_path + [peth, 'mac', mac_address])
            self.cli_set(self._base_path + [peth, 'anycast-gateway'])
        self.cli_commit()

        fdb = cmdl(['bridge', 'fdb', 'show', 'dev', br])
        for vlan in vlans:
            self.assertIn(f'{mac_address} vlan {vlan} master {br} permanent', fdb)

        # A second anycast-gateway with the same MAC on the same VLAN is invalid
        self.cli_set(self._base_path + ['peth999', 'source-interface', f'{br}.{vlans[0]}'])
        self.cli_set(self._base_path + ['peth999', 'mac', mac_address])
        self.cli_set(self._base_path + ['peth999', 'anycast-gateway'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(self._base_path + ['peth999'])

        # Removing one gateway must leave the other VLANs untouched
        self.cli_delete(self._base_path + [f'peth{vlans[0]}'])
        self.cli_commit()

        fdb = cmdl(['bridge', 'fdb', 'show', 'dev', br])
        self.assertNotIn(f'{mac_address} vlan {vlans[0]} master {br} permanent', fdb)
        for vlan in vlans[1:]:
            self.assertIn(f'{mac_address} vlan {vlan} master {br} permanent', fdb)

        self.cli_delete(self._base_path)
        self.cli_delete(base_bridge_path)
        self.cli_commit()


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
