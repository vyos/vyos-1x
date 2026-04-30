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
from vyos.utils.process import cmd

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
                fdb = cmd(f'bridge fdb show dev {br}')
                self.assertIn(f'{mac_address} master {br} permanent', fdb)
                self.assertIn(f'{mac_address} self permanent', fdb)

                # Then remove just the anycast-gateway flag
                self.cli_delete(self._base_path + [peth, 'anycast-gateway'])
                self.cli_commit()

                fdb = cmd(f'bridge fdb show dev {br}')
                self.assertNotIn(f'{mac_address} master {br} permanent', fdb)

                # Clean up temp bridge and peth
                self.cli_delete(self._base_path + [peth])
                self.cli_delete(base_bridge_path)
                self.cli_commit()


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
