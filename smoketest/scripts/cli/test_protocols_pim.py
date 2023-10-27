#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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
from vyos.ifconfig import Section
from vyos.utils.process import process_named_running

PROCESS_NAME = 'pimd'
base_path = ['protocols', 'pim']

class TestProtocolsPIM(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))
        self.cli_delete(base_path)
        self.cli_commit()

    def test_pim_01_simple(self):
        rp = '127.0.0.1'
        group = '224.0.0.0/4'
        hello = '100'
        # commit changes

        self.cli_set(base_path + ['rp', 'address', rp, 'group', group])
        interfaces = Section.interfaces('ethernet')

        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface])
            self.cli_set(base_path + ['interface', interface , 'hello', hello])
            self.cli_set(base_path + ['interface', interface , 'bfd', 'enable'])

        self.cli_commit()


        # Verify FRR pimd configuration
        frrconfig = self.getFRRconfig('ip pim rp {rp} {group}', daemon=PROCESS_NAME)

        for interface in interfaces:
            frrconfig = self.getFRRconfig(
                f'interface {interface}', daemon=PROCESS_NAME)
            self.assertIn(f'interface {interface}', frrconfig)
            self.assertIn(f' ip pim', frrconfig)
            self.assertIn(f' ip pim bfd', frrconfig)
            self.assertIn(f' ip pim hello {hello}', frrconfig)

        self.cli_commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
