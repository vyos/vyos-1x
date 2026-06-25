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


import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.utils.system import sysctl_read
from vyos.utils.process import cmd

base_path = ['protocols', 'static', 'neighbor-proxy']
interface = 'eth0'


class TestProtocolsStaticNeighborProxy(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProtocolsStaticNeighborProxy, cls).setUpClass()
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()
        super().tearDown()

    def test_arp_proxy(self):
        address = '192.0.2.1/24'
        neighbor = '192.0.2.10'

        self.cli_set(['interfaces', 'ethernet', interface, 'address', address])
        self.cli_set(base_path + ['arp', neighbor, 'interface', interface])
        self.cli_commit()

        proxy_entries = cmd('ip -4 neigh show proxy')
        self.assertIn(f'{neighbor} dev {interface} proxy', proxy_entries)

        self.cli_delete(['interfaces', 'ethernet', interface, 'address', address])

    def test_nd_proxy(self):
        address = 'fd00::1/64'
        neighbor = 'fd00::99'
        interface2 = 'eth1'

        self.cli_set(['interfaces', 'ethernet', interface, 'address', address])
        # Add ND proxy on two interfaces
        self.cli_set(base_path + ['nd', neighbor, 'interface', interface])
        self.cli_set(base_path + ['nd', neighbor, 'interface', interface2])
        self.cli_commit()

        # Verify proxy entries are installed
        proxy_entries = cmd('ip -6 neigh show proxy')
        for iface in [interface, interface2]:
            self.assertIn(f'{neighbor} dev {iface} proxy', proxy_entries)
            # Verify proxy_ndp sysctl is enabled on both interfaces
            self.assertEqual(
                sysctl_read(['net', 'ipv6', 'conf', iface, 'proxy_ndp']), '1'
            )

        # Remove one interface
        self.cli_delete(base_path + ['nd', neighbor, 'interface', interface2])
        self.cli_commit()

        # First interface still enabled
        self.assertEqual(
            sysctl_read(['net', 'ipv6', 'conf', interface, 'proxy_ndp']), '1'
        )
        # Removed interface disabled
        self.assertEqual(
            sysctl_read(['net', 'ipv6', 'conf', interface2, 'proxy_ndp']), '0'
        )

        self.cli_delete(['interfaces', 'ethernet', interface, 'address', address])


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
