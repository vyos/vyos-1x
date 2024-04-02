#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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

from vyos.utils.process import cmd
from vyos.utils.network import is_netns_interface
from vyos.utils.network import get_netns_all

base_path = ['netns']
interfaces = ['dum10', 'dum12', 'dum50']

class NetNSTest(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        self.cli_delete(base_path)
        # commit changes
        self.cli_commit()

        # There should be no network namespace remaining
        tmp = cmd('ip netns ls')
        self.assertFalse(tmp)

        super(NetNSTest, self).tearDown()

    def test_netns_create(self):
        namespaces = ['mgmt', 'front', 'back']
        for netns in namespaces:
            self.cli_set(base_path + ['name', netns])

        # commit changes
        self.cli_commit()

        # Verify NETNS configuration
        for netns in namespaces:
            self.assertIn(netns, get_netns_all())

    def test_netns_interface(self):
        netns = 'foo'
        self.cli_set(base_path + ['name', netns])

        # Set
        for iface in interfaces:
            self.cli_set(['interfaces', 'dummy', iface, 'netns', netns])

        # commit changes
        self.cli_commit()

        for interface in interfaces:
            self.assertTrue(is_netns_interface(interface, netns))

        # Delete
        for interface in interfaces:
            self.cli_delete(['interfaces', 'dummy', interface])

        # commit changes
        self.cli_commit()

        netns_iface_list = cmd(f'sudo ip netns exec {netns} ip link show')

        for interface in interfaces:
            self.assertFalse(is_netns_interface(interface, netns))

if __name__ == '__main__':
    unittest.main(verbosity=2)
