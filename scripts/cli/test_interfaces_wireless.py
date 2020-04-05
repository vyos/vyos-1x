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

    def test_wifi_client(self):
        """ test creation of a wireless station """
        for intf in self._interfaces:
            # prepare interfaces
            for option in self._options.get(intf, []):
                self.session.set(self._base_path + [intf] + option.split())

            # commit changes
            self.session.commit()



if __name__ == '__main__':
    os.system("modprobe mac80211_hwsim")
    unittest.main()
