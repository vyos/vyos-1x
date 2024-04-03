#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
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

import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.ifconfig import Section
from vyos.utils.process import cmd
from vyos.utils.process import process_named_running

PROCESS_NAME = 'ndppd'
NDPPD_CONF = '/run/ndppd/ndppd.conf'
base_path = ['service', 'ndp-proxy']

def getConfigSection(string=None, end=' {', endsection='^}'):
    tmp = f'cat {NDPPD_CONF} | sed -n "/^{string}{end}/,/{endsection}/p"'
    out = cmd(tmp)
    return out

class TestServiceNDPProxy(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestServiceNDPProxy, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        # delete testing SSH config
        self.cli_delete(base_path)
        self.cli_commit()

        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_basic(self):
        interfaces = Section.interfaces('ethernet')
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface])
            self.cli_set(base_path + ['interface', interface, 'enable-router-bit'])

        self.cli_commit()

        for interface in interfaces:
            config = getConfigSection(f'proxy {interface}')
            self.assertIn(f'proxy {interface}', config)
            self.assertIn(f'router yes', config)
            self.assertIn(f'timeout 500', config) # default value
            self.assertIn(f'ttl 30000', config) # default value

if __name__ == '__main__':
    unittest.main(verbosity=2)
