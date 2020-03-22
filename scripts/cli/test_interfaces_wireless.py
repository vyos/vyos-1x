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

import os
import unittest

from base_interfaces_test import BasicInterfaceTest

class WirelessInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
        super().setUp()

        self._base_path = ['interfaces', 'wireless']
        self._interfaces = ['wlan0']

        def test_add_description(self):
            """
            A physical interface is mandatory thus we overwrite this function.
            """
            for intf in self._interfaces:
                self.session.set(self._base_path + [intf, 'physical-device', 'phy0'])

            super.test_add_description()

        def test_add_address(self):
            """
            A physical interface is mandatory thus we overwrite this function.
            """
            for intf in self._interfaces:
                self.session.set(self._base_path + [intf, 'physical-device', 'phy0'])

            super.test_add_address()

if __name__ == '__main__':
    os.system("modprobe mac80211_hwsim")
    unittest.main()
