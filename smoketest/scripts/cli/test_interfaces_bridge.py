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
from glob import glob
from netifaces import interfaces
from vyos.ifconfig import Section

class BridgeInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
        super().setUp()

        self._test_ipv6 = True

        self._base_path = ['interfaces', 'bridge']
        self._interfaces = ['br0']

        self._members = []
        # we need to filter out VLAN interfaces identified by a dot (.)
        # in their name - just in case!
        if 'TEST_ETH' in os.environ:
            self._members = os.environ['TEST_ETH'].split()
        else:
            for tmp in Section.interfaces("ethernet"):
                if not '.' in tmp:
                    self._members.append(tmp)

        self._options['br0'] = []
        for member in self._members:
            self._options['br0'].append(f'member interface {member}')

    def test_add_remove_member(self):
        """ Add member interfaces to bridge and set STP cost/priority """
        for interface in self._interfaces:
            base = self._base_path + [interface]
            self.session.set(base + ['stp'])
            self.session.set(base + ['address', '192.0.2.1/24'])

            cost = 1000
            priority = 10
            # assign members to bridge interface
            for member in self._members:
                base_member = base + ['member', 'interface', member]
                self.session.set(base_member + ['cost', str(cost)])
                self.session.set(base_member + ['priority', str(priority)])
                cost += 1
                priority += 1

        # commit config
        self.session.commit()

        # check member interfaces are added on the bridge
        bridge_members = []
        for tmp in glob(f'/sys/class/net/{interface}/lower_*'):
            bridge_members.append(os.path.basename(tmp).replace('lower_', ''))

        for member in self._members:
            self.assertIn(member, bridge_members)

        # delete all members
        for interface in self._interfaces:
            self.session.delete(self._base_path + [interface, 'member'])

        self.session.commit()

    def test_vlan_members(self):
        """ T2945: ensure that VIFs are not dropped from bridge """

        self.session.set(['interfaces', 'ethernet', 'eth0', 'vif', '300'])
        self.session.set(['interfaces', 'bridge', 'br0', 'member', 'interface', 'eth0.300'])
        self.session.commit()

        # member interface must be assigned to the bridge
        self.assertTrue(os.path.exists('/sys/class/net/br0/lower_eth0.300'))

        # add second bridge member
        self.session.set(['interfaces', 'ethernet', 'eth0', 'vif', '400'])
        self.session.commit()

        # member interface must still be assigned to the bridge
        self.assertTrue(os.path.exists('/sys/class/net/br0/lower_eth0.300'))

        # remove VLAN interfaces
        self.session.delete(['interfaces', 'ethernet', 'eth0', 'vif', '300'])
        self.session.delete(['interfaces', 'ethernet', 'eth0', 'vif', '400'])
        self.session.commit()


if __name__ == '__main__':
    unittest.main()

