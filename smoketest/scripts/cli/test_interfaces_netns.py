#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

import re
import os
import json
import unittest

from netifaces import interfaces
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Interface
from vyos.ifconfig import Section
from vyos.util import cmd

base_path = ['netns']
namespaces = ['mgmt', 'front', 'back', 'ams-ix']

class NETNSTest(VyOSUnitTestSHIM.TestCase):

    def setUp(self):
        self._interfaces = ['dum10', 'dum12', 'dum50']

    def test_create_netns(self):
        for netns in namespaces:
            base = base_path + ['name', netns]
            self.cli_set(base)

        # commit changes
        self.cli_commit()

        netns_list = cmd('ip netns ls')

        # Verify NETNS configuration
        for netns in namespaces:
            self.assertTrue(netns in netns_list)


    def test_netns_assign_interface(self):
        netns = 'foo'
        self.cli_set(['netns', 'name', netns])

        # Set
        for iface in self._interfaces:
            self.cli_set(['interfaces', 'dummy', iface, 'netns', netns])

        # commit changes
        self.cli_commit()

        netns_iface_list = cmd(f'sudo ip netns exec {netns} ip link show')

        for iface in self._interfaces:
            self.assertTrue(iface in netns_iface_list)

        # Delete
        for iface in self._interfaces:
            self.cli_delete(['interfaces', 'dummy', iface, 'netns', netns])

        # commit changes
        self.cli_commit()

        netns_iface_list = cmd(f'sudo ip netns exec {netns} ip link show')

        for iface in self._interfaces:
            self.assertNotIn(iface, netns_iface_list)

if __name__ == '__main__':
    unittest.main(verbosity=2)
