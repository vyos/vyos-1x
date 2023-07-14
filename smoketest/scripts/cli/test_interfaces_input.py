#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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

from vyos.utils.file import read_file
from vyos.ifconfig import Interface
from base_vyostest_shim import VyOSUnitTestSHIM

base_path = ['interfaces', 'input']

# add a classmethod to setup a temporaray PPPoE server for "proper" validation
class InputInterfaceTest(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(InputInterfaceTest, cls).setUpClass()
        cls._interfaces = ['ifb10', 'ifb20', 'ifb30']

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_01_description(self):
        # Check if PPPoE dialer can be configured and runs
        for interface in self._interfaces:
            self.cli_set(base_path + [interface, 'description', f'foo-{interface}'])

        # commit changes
        self.cli_commit()

        # Validate remove interface description "empty"
        for interface in self._interfaces:
            tmp = read_file(f'/sys/class/net/{interface}/ifalias')
            self.assertEqual(tmp, f'foo-{interface}')
            self.assertEqual(Interface(interface).get_alias(), f'foo-{interface}')

if __name__ == '__main__':
    unittest.main(verbosity=2)
