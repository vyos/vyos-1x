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
from vyos.interfaces import list_interfaces_of_type

class BondingInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
         super().setUp()

         self._base_path = ['interfaces', 'bonding']
         self._test_mtu = True
         self._interfaces = ['bond0']

    def test_add_remove_member(self):
        members = []
        # we need to filter out VLAN interfaces identified by a dot (.)
        # in their name - just in case!
        for tmp in list_interfaces_of_type("ethernet"):
            if not '.' in tmp:
                members.append(tmp)

        for intf in self._interfaces:
            for member in members:
                # We can not enslave an interface when there is an address
                # assigned - take care here - or find them dynamically if a user
                # runs vyos-smoketest on his production device?
                self.session.set(self._base_path + [intf, 'member', 'interface', member])

        self.session.commit()

        # check validate() - we can only add existing interfaces
        self.session.set(self._base_path + [intf, 'member', 'interface', 'eth99'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

        # check if member deletion works as expected
        self.session.delete(self._base_path + [intf, 'member'])
        self.session.commit()

if __name__ == '__main__':
    unittest.main()
