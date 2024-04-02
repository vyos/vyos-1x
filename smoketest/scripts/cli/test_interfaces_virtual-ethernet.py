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

from netifaces import interfaces

from vyos.utils.process import process_named_running
from base_interfaces_test import BasicInterfaceTest

class VEthInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'virtual-ethernet']
        cls._options = {
            'veth0': ['peer-name veth1'],
            'veth1': ['peer-name veth0'],
        }

        cls._interfaces = list(cls._options)
        # call base-classes classmethod
        super(VEthInterfaceTest, cls).setUpClass()

    def test_vif_8021q_mtu_limits(self):
        self.skipTest('not supported')

    # As we always need a pair of veth interfaces, we can not rely on the base
    # class check to determine if there is a dhcp6c or dhclient instance running.
    # This test will always fail as there is an instance running on the peer
    # interface.
    def tearDown(self):
        self.cli_delete(self._base_path)
        self.cli_commit()

        # Verify that no previously interface remained on the system
        for intf in self._interfaces:
            self.assertNotIn(intf, interfaces())

    @classmethod
    def tearDownClass(cls):
        # No daemon started during tests should remain running
        for daemon in ['dhcp6c', 'dhclient']:
            cls.assertFalse(cls, process_named_running(daemon))

        super(VEthInterfaceTest, cls).tearDownClass()

if __name__ == '__main__':
    unittest.main(verbosity=2)
