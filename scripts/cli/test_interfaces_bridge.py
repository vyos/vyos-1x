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

from base_interfaces_test import *
from vyos.interfaces import list_interfaces_of_type

class BridgeInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
        super().setUp()

        self._base_path = ['interfaces', 'bridge']
        self._interfaces = ['br0']

    def test_add_remove_member(self):
        members = []
        # we need to filter out VLAN interfaces identified by a dot (.)
        # in their name - just in case!
        for tmp in list_interfaces_of_type("ethernet"):
            if not '.' in tmp:
                members.append(tmp)

        for intf in self._interfaces:
            cost = 1000
            priority = 10

            self.session.set(self._base_path + [intf, 'stp'])

            # assign members to bridge interface
            for member in members:
                self.session.set(self._base_path + [intf, 'member', 'interface', member])
                self.session.set(self._base_path + [intf, 'member', 'interface', member, 'cost', str(cost)])
                self.session.set(self._base_path + [intf, 'member', 'interface', member, 'priority', str(priority)])
                cost += 1
                priority += 1

        self.session.commit()

        for intf in self._interfaces:
            self.session.delete(self._base_path + [intf, 'member'])

        self.session.commit()

if __name__ == '__main__':
    unittest.main()
