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
from psutil import process_iter
from vyos.util import check_kmod

class WirelessInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
        super().setUp()

        self._base_path = ['interfaces', 'wireless']
        self._options = {
            'wlan0':  ['physical-device phy0', 'ssid VyOS-WIFI-0',
                       'type station', 'address 192.0.2.1/30'],
            'wlan1':  ['physical-device phy0', 'ssid VyOS-WIFI-1',
                       'type access-point', 'address 192.0.2.5/30', 'channel 0'],
            'wlan10': ['physical-device phy1', 'ssid VyOS-WIFI-2',
                       'type station', 'address 192.0.2.9/30'],
            'wlan11': ['physical-device phy1', 'ssid VyOS-WIFI-3',
                       'type access-point', 'address 192.0.2.13/30', 'channel 0'],
        }
        self._interfaces = list(self._options)
        self.session.set(['system', 'wifi-regulatory-domain', 'SE'])

    def test_add_address_single(self):
        """ derived method to check if member interfaces are enslaved properly """
        super().test_add_address_single()

        for option, option_value in self._options.items():
            if 'type access-point' in option_value:
                # Check for running process
                self.assertIn('hostapd', (p.name() for p in process_iter()))
            elif 'type station' in option_value:
                # Check for running process
                self.assertIn('wpa_supplicant', (p.name() for p in process_iter()))
            else:
                self.assertTrue(False)

if __name__ == '__main__':
    check_kmod('mac80211_hwsim')
    unittest.main()
