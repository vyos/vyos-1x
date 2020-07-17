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

from vyos.ifconfig import Section
from vyos.configsession import ConfigSessionError
from vyos.util import read_file

class BondingInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
         super().setUp()

         self._base_path = ['interfaces', 'bonding']
         self._interfaces = ['bond0']
         self._test_mtu = True
         self._test_vlan = True
         self._test_qinq = True

    def test_add_member(self):
        members = []
        # we need to filter out VLAN interfaces identified by a dot (.)
        # in their name - just in case!
        if 'TEST_ETH' in os.environ:
            members = os.environ['TEST_ETH'].split()
        else:
            for tmp in Section.interfaces("ethernet"):
                if not '.' in tmp:
                    members.append(tmp)

        for interface in self._interfaces:
            base = self._base_path + [interface]
            for member in members:
                # We can not enslave an interface when there is an address
                # assigned - take care here - or find them dynamically if a user
                # runs vyos-smoketest on his production device?
                self.session.set(base + ['member', 'interface', member])

        self.session.commit()

        for interface in self._interfaces:
            slaves = read_file(f'/sys/class/net/{interface}/bonding/slaves').split()
            self.assertListEqual(slaves, members)

if __name__ == '__main__':
    unittest.main()
