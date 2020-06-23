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

from vyos.ifconfig import Section
from base_interfaces_test import BasicInterfaceTest

class MACsecInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
         super().setUp()
         self._base_path = ['interfaces', 'macsec']
         self._options = {
             'macsec0': ['source-interface eth0',
                         'security cipher gcm-aes-128',
                         'security encrypt',
                         'security mka cak 232e44b7fda6f8e2d88a07bf78a7aff4',
                         'security mka ckn 40916f4b23e3d548ad27eedd2d10c6f98c2d21684699647d63d41b500dfe8836',
                         'security replay-window 128']
         }

         # if we have a physical eth1 interface, add a second macsec instance
         if 'eth1' in Section.interfaces("ethernet"):
             macsec = { 'macsec1': ['source-interface eth1', 'security cipher gcm-aes-128'] }
             self._options.update(macsec)

         self._interfaces = list(self._options)

if __name__ == '__main__':
    unittest.main()
