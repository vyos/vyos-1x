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
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSession
from vyos.util import read_file
from vyos.util import process_named_running

UPNP_CONF = '/run/upnp/miniupnp.conf'
interface = 'eth0'
base_path = ['service', 'upnp']
address_base = ['interfaces', 'ethernet', interface, 'address']

class TestServiceUPnP(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        self.cli_delete(address_base)
        self.cli_delete(base_path)
        self.cli_commit()
    
    def test_ipv4_base(self):
        self.cli_set(address_base + ['100.64.0.1/24'])
        self.cli_set(base_path + ['nat-pmp'])
        self.cli_set(base_path + ['wan-interface', interface])
        self.cli_set(base_path + ['listen', interface])
        self.cli_commit()
        
        config = read_file(UPNP_CONF)
        self.assertIn(f'ext_ifname={interface}', config)
        self.assertIn(f'listening_ip={interface}', config)
        self.assertIn(f'enable_natpmp=yes', config)
        self.assertIn(f'enable_upnp=yes', config)
        
        # Check for running process
        self.assertTrue(process_named_running('miniupnpd'))
    
    def test_ipv6_base(self):
        self.cli_set(address_base + ['2001:db8::1/64'])
        self.cli_set(base_path + ['nat-pmp'])
        self.cli_set(base_path + ['wan-interface', interface])
        self.cli_set(base_path + ['listen', interface])
        self.cli_set(base_path + ['listen', '2001:db8::1'])
        self.cli_commit()
        
        config = read_file(UPNP_CONF)
        self.assertIn(f'ext_ifname={interface}', config)
        self.assertIn(f'listening_ip={interface}', config)
        self.assertIn(f'enable_natpmp=yes', config)
        self.assertIn(f'enable_upnp=yes', config)
        
        # Check for running process
        self.assertTrue(process_named_running('miniupnpd'))

if __name__ == '__main__':
    unittest.main(verbosity=2)
