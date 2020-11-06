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

base_path = ['service','proxy-ndp']

class TaskNdpProxy(unittest.TestCase):
    def setUp(self):
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        self.session = ConfigSession(os.getpid())
        self.session.delete(base_path)

    def tearDown(self):
        self.session.delete(base_path)
        self.session.commit()
    def test_ndp_proxy(self):
        self.session.set(base_path + ['interface','eth0','ttl'],30000)
        self.session.set(base_path + ['interface','eth0','timeout'],500)
        self.session.set(base_path + ['interface','eth0','prefix','fc00::/64','mode'],'auto')
        # check validate() - outbound-interface must be defined
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(base_path + ['interface','eth0','prefix','fc00::/64','mode'],'static')
        # check validate() - outbound-interface must be defined
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(base_path + ['interfaces','eth0','prefix','fc00::/64','mode'],'iface')
        self.session.set(base_path + ['interfaces','eth0','prefix','fc00::/64','iface'],'eth0')
        # check validate() - outbound-interface must be defined
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        with open(f'/proc/sys/net/ipv6/conf/eth0/proxy_ndp', 'r') as f:
            flags = f.read()
            self.assertEqual(int(flags), 1)
        self.assertEqual(True)

if __name__ == '__main__':
    unittest.main()
