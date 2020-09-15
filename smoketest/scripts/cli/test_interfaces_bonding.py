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
from vyos.ifconfig.interface import Interface
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
        self._test_ipv6 = True

        self._members = []
        # we need to filter out VLAN interfaces identified by a dot (.)
        # in their name - just in case!
        if 'TEST_ETH' in os.environ:
            self._members = os.environ['TEST_ETH'].split()
        else:
            for tmp in Section.interfaces("ethernet"):
                if not '.' in tmp:
                    self._members.append(tmp)

        self._options['bond0'] = []
        for member in self._members:
            self._options['bond0'].append(f'member interface {member}')


    def test_add_address_single(self):
        """ derived method to check if member interfaces are enslaved properly """
        super().test_add_address_single()

        for interface in self._interfaces:
            slaves = read_file(f'/sys/class/net/{interface}/bonding/slaves').split()
            self.assertListEqual(slaves, self._members)

    def test_remove_member(self):
        """ T2515: when removing a bond member the interface must be admin-up again """

        # configure member interfaces
        for interface in self._interfaces:
            for option in self._options.get(interface, []):
                self.session.set(self._base_path + [interface] + option.split())

        self.session.commit()

        # remove single bond member port
        for interface in self._interfaces:
            remove_member = self._members[0]
            self.session.delete(self._base_path + [interface, 'member', 'interface', remove_member])

        self.session.commit()

        # removed member port must be admin-up
        for interface in self._interfaces:
            remove_member = self._members[0]
            state = Interface(remove_member).get_admin_state()
            self.assertEqual('up', state)

if __name__ == '__main__':
    unittest.main()
