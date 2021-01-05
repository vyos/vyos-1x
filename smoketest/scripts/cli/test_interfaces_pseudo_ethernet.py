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

class PEthInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
        self._test_ip = True
        self._test_ipv6 = True
        self._test_mtu = True
        self._test_vlan = True
        self._test_qinq = True
        self._base_path = ['interfaces', 'pseudo-ethernet']
        self._options = {
            'peth0': ['source-interface eth1'],
            'peth1': ['source-interface eth1'],
        }
        self._interfaces = list(self._options)
        super().setUp()

if __name__ == '__main__':
    unittest.main(verbosity=2)
