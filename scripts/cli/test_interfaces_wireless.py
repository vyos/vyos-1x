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
        self._interfaces = ['wlan0', 'wlan1', 'wlan10', 'wlan11']
        self._options = {
            'wlan0': ['physical-device phy0'],
            'wlan1': ['physical-device phy0'],
            'wlan10': ['physical-device phy1'],
            'wlan11': ['physical-device phy1'],
        }


if __name__ == '__main__':
    os.system("modprobe mac80211_hwsim")
    unittest.main()
