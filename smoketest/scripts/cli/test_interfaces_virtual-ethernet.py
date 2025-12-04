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

from base_interfaces_test import BasicInterfaceTest
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.network import interface_exists

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

    def test_invalid_peers(self):
        peer = ('veth1001', 'veth1002')
        self.cli_set(self._base_path + [peer[0]])
        self.cli_set(self._base_path + [peer[1], 'peer-name', peer[0]])

        # Configuration mismatch between "veth1001" and "veth1001"
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(self._base_path + [peer[0], 'peer-name', peer[1]])
        self.cli_commit()

        self.assertTrue(interface_exists(peer[0]))
        self.assertTrue(interface_exists(peer[1]))

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
