#!/usr/bin/env python3
#
# Copyright (C) 2020-2023 VyOS maintainers and contributors
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

from base_interfaces_test import BasicInterfaceTest
from netifaces import interfaces

from vyos.utils.network import is_intf_addr_assigned

loopbacks = ['127.0.0.1', '::1']

class LoopbackInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'loopback']
        cls._interfaces = ['lo']
        # call base-classes classmethod
        super(LoopbackInterfaceTest, cls).setUpClass()

    # we need to override tearDown() as loopback interfaces are ephemeral and
    # will always be present on the system - the base class check will fail as
    # the loopback interface will still exist.
    def tearDown(self):
        self.cli_delete(self._base_path)
        self.cli_commit()

        # loopback interface must persist!
        for intf in self._interfaces:
            self.assertIn(intf, interfaces())

    def test_add_single_ip_address(self):
        super().test_add_single_ip_address()
        for addr in loopbacks:
            self.assertTrue(is_intf_addr_assigned('lo', addr))

    def test_add_multiple_ip_addresses(self):
        super().test_add_multiple_ip_addresses()
        for addr in loopbacks:
            self.assertTrue(is_intf_addr_assigned('lo', addr))

    def test_interface_disable(self):
        self.skipTest('not supported')

if __name__ == '__main__':
    unittest.main(verbosity=2)
