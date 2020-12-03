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

class EthernetInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
        super().setUp()

        self._base_path = ['interfaces', 'ethernet']
        self._test_ip = True
        self._test_mtu = True
        self._test_vlan = True
        self._test_qinq = True
        self._test_ipv6 = True
        self._test_mirror = True
        self._interfaces = []

        # we need to filter out VLAN interfaces identified by a dot (.)
        # in their name - just in case!
        if 'TEST_ETH' in os.environ:
            tmp = os.environ['TEST_ETH'].split()
            self._interfaces = tmp
        else:
            for tmp in Section.interfaces("ethernet"):
                if not '.' in tmp:
                    self._interfaces.append(tmp)

        def test_dhcp_disable(self):
            """
            When interface is configured as admin down, it must be admin down even
            """
            for interface in self._interfaces:
                self.session.set(self._base_path + [interface, 'disable'])
                for option in self._options.get(interface, []):
                    self.session.set(self._base_path + [interface] + option.split())

                # Also enable DHCP (ISC DHCP always places interface in admin up
                # state so we check that we do not start DHCP client.
                # https://phabricator.vyos.net/T2767
                self.session.set(self._base_path + [interface, 'address', 'dhcp'])

            self.session.commit()

            # Validate interface state
            for interface in self._interfaces:
                with open(f'/sys/class/net/{interface}/flags', 'r') as f:
                    flags = f.read()
                self.assertEqual(int(flags, 16) & 1, 0)

if __name__ == '__main__':
    unittest.main()
