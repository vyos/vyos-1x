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

from base_interfaces_test import BasicInterfaceTest
from vyos.interfaces import list_interfaces_of_type

class EthernetInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
        super().setUp()

        self._base_path = ['interfaces', 'ethernet']
        self._test_mtu = True
        self._interfaces = []

        # we need to filter out VLAN interfaces identified by a dot (.)
        # in their name - just in case!
        for tmp in list_interfaces_of_type("ethernet"):
            if not '.' in tmp:
                self._interfaces.append(tmp)


if __name__ == '__main__':
    unittest.main()
