#!/usr/bin/env python3
#
# Copyright (C) 2021-2022 VyOS maintainers and contributors
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
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.template import ip_from_cidr
from vyos.util import read_file
from vyos.util import process_named_running

UPNP_CONF = '/run/upnp/miniupnp.conf'
DAEMON = 'miniupnpd'
interface = 'eth0'
base_path = ['service', 'upnp']
address_base = ['interfaces', 'ethernet', interface, 'address']

ipv4_addr = '100.64.0.1/24'
ipv6_addr = '2001:db8::1/64'

class TestServiceUPnP(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestServiceUPnP, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

        cls.cli_set(cls, address_base + [ipv4_addr])
        cls.cli_set(cls, address_base + [ipv6_addr])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, address_base)
        cls._session.commit()

        super(TestServiceUPnP, cls).tearDownClass()

    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(DAEMON))

        self.cli_delete(base_path)
        self.cli_commit()

        # Check for running process
        self.assertFalse(process_named_running(DAEMON))

    def test_ipv4_base(self):
        self.cli_set(base_path + ['nat-pmp'])
        self.cli_set(base_path + ['listen', interface])

        # check validate() - WAN interface is mandatory
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['wan-interface', interface])

        self.cli_commit()

        config = read_file(UPNP_CONF)
        self.assertIn(f'ext_ifname={interface}', config)
        self.assertIn(f'listening_ip={interface}', config)
        self.assertIn(f'enable_natpmp=yes', config)
        self.assertIn(f'enable_upnp=yes', config)

    def test_ipv6_base(self):
        v6_addr = ip_from_cidr(ipv6_addr)

        self.cli_set(base_path + ['nat-pmp'])
        self.cli_set(base_path + ['listen', interface])
        self.cli_set(base_path + ['listen', v6_addr])

        # check validate() - WAN interface is mandatory
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['wan-interface', interface])

        self.cli_commit()

        config = read_file(UPNP_CONF)
        self.assertIn(f'ext_ifname={interface}', config)
        self.assertIn(f'listening_ip={interface}', config)
        self.assertIn(f'ipv6_listening_ip={v6_addr}', config)
        self.assertIn(f'enable_natpmp=yes', config)
        self.assertIn(f'enable_upnp=yes', config)

if __name__ == '__main__':
    unittest.main(verbosity=2)
