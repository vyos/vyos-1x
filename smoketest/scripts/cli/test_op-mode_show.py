#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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

from vyos.utils.process import cmd
from vyos.version import get_version

base_path = ['show']

class TestOPModeShow(VyOSUnitTestSHIM.TestCase):
    def test_op_mode_show_version(self):
        # Retrieve output of "show version" OP-mode command
        tmp = self.op_mode(base_path + ['version'])
        # Validate
        version = get_version()
        self.assertIn(f'Version:          VyOS {version}', tmp)

    def test_op_mode_show_version_kernel(self):
        # Retrieve output of "show version" OP-mode command
        tmp = self.op_mode(base_path + ['version', 'kernel'])
        self.assertEqual(cmd('uname -r'), tmp)

    def test_op_mode_show_vrf(self):
        # Retrieve output of "show version" OP-mode command
        tmp = self.op_mode(base_path + ['vrf'])
        # Validate
        self.assertIn('VRF is not configured', tmp)

if __name__ == '__main__':
    unittest.main(verbosity=2)
