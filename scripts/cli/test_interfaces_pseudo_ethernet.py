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
         super().setUp()
         self._base_path = ['interfaces', 'pseudo-ethernet']
         options = ['source-interface eth0', 'ip arp-cache-timeout 10',
                    'ip disable-arp-filter', 'ip enable-arp-accept',
                    'ip enable-arp-announce', 'ip enable-arp-ignore',
                    'ip enable-proxy-arp', 'ip proxy-arp-pvlan']

         self._options = {
             'peth0': options,
             'peth1': options,
         }
         self._interfaces = list(self._options)

if __name__ == '__main__':
    unittest.main()
