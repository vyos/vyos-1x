#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
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

from vyos.ifconfig import Interface
from vyos.utils.network import is_intf_addr_assigned

class VTIInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'vti']
        cls._interfaces = ['vti10', 'vti20', 'vti30']

        # call base-classes classmethod
        super(VTIInterfaceTest, cls).setUpClass()

    def test_add_single_ip_address(self):
        addr = '192.0.2.0/31'
        for intf in self._interfaces:
            self.cli_set(self._base_path + [intf, 'address', addr])
            for option in self._options.get(intf, []):
                self.cli_set(self._base_path + [intf] + option.split())

        self.cli_commit()

        # VTI interface are always down and only brought up by IPSec
        for intf in self._interfaces:
            self.assertTrue(is_intf_addr_assigned(intf, addr))
            self.assertEqual(Interface(intf).get_admin_state(), 'down')

if __name__ == '__main__':
    unittest.main(verbosity=2)
