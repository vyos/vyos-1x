#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.process import cmd
from vyos.utils.process import process_named_running

base_path = ['protocols', 'segment-routing']
PROCESS_NAME = 'zebra'

class TestProtocolsSegmentRouting(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        # call base-classes classmethod
        super(TestProtocolsSegmentRouting, cls).setUpClass()
        # Retrieve FRR daemon PID - it is not allowed to crash, thus PID must remain the same
        cls.daemon_pid = process_named_running(PROCESS_NAME)
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        # check process health and continuity
        self.assertEqual(self.daemon_pid, process_named_running(PROCESS_NAME))

    def test_srv6(self):
        locators = {
            'foo' : { 'prefix' : '2001:a::/64' },
            'foo' : { 'prefix' : '2001:b::/64', 'usid' : {} },
        }

        for locator, locator_config in locators.items():
            self.cli_set(base_path + ['srv6', 'locator', locator, 'prefix', locator_config['prefix']])
            if 'usid' in locator_config:
                self.cli_set(base_path + ['srv6', 'locator', locator, 'behavior-usid'])

        self.cli_commit()

        frrconfig = self.getFRRconfig(f'segment-routing', daemon='zebra')
        self.assertIn(f'segment-routing', frrconfig)
        self.assertIn(f' srv6', frrconfig)
        self.assertIn(f'  locators', frrconfig)
        for locator, locator_config in locators.items():
            self.assertIn(f'   locator {locator}', frrconfig)
            self.assertIn(f'    prefix {locator_config["prefix"]} block-len 40 node-len 24 func-bits 16', frrconfig)


if __name__ == '__main__':
    unittest.main(verbosity=2)
