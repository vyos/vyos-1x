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

import unittest

from base_interfaces_test import BasicInterfaceTest
from vyos.validate import is_intf_addr_assigned

class LoopbackInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
         super().setUp()
         # these addresses are never allowed to be removed from the system
         self._loopback_addresses = ['127.0.0.1', '::1']
         self._base_path = ['interfaces', 'loopback']
         self._interfaces = ['lo']

    def test_add_single_ip_address(self):
        super().test_add_single_ip_address()
        for addr in self._loopback_addresses:
            self.assertTrue(is_intf_addr_assigned('lo', addr))

    def test_add_multiple_ip_addresses(self):
        super().test_add_multiple_ip_addresses()
        for addr in self._loopback_addresses:
            self.assertTrue(is_intf_addr_assigned('lo', addr))

if __name__ == '__main__':
    unittest.main(verbosity=2)
