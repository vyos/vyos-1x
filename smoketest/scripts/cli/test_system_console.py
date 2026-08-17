#!/usr/bin/env python3
#
# Copyright (C) VyOS Inc.
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

from vyos.configsession import ConfigSessionError
from vyos.system import disk
from vyos.system.grub import CFG_VYOS_VARS
from vyos.system.grub import vars_read
from vyos.xml_ref import default_value

base_path = ['system', 'console']
serial_console = 'ttyS0'
default_speed = default_value(base_path + ['device', serial_console, 'speed'])

def get_grub_vars() -> dict:
    root_dir = disk.find_persistence()
    vars_file: str = f'{root_dir}/{CFG_VYOS_VARS}'
    vars_current: dict[str, str] = vars_read(vars_file)
    return vars_current

class TestSystemConsole(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSystemConsole, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)
        cls.cli_commit(cls)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()
        # always forward to base class
        super().tearDown()

    def test_multiple_kernel_consoles(self):
        self.cli_set(base_path + ['device', 'ttyS1', 'kernel'])
        self.cli_set(base_path + ['device', 'ttyS2', 'kernel'])

        # Only one console can have 'kernel'
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

    def test_fbcon_and_serial_con_switch(self):
        if not self.running_in_smoketest_harness():
            self.skipTest('Not running under VyOS CI/CD QEMU environment!')

        grub_vars = get_grub_vars()
        # we have deleted the CLI config in tearDown() so the default is now
        # the framebuffer console at tty0
        self.assertEqual(grub_vars['console_type'], 'tty')

        self.cli_set(base_path + ['device', serial_console, 'kernel'])
        self.cli_commit()

        grub_vars = get_grub_vars()
        # We moved the Kernel boot console to ttyS0
        self.assertEqual(grub_vars['console_type'], serial_console[:-1])
        self.assertEqual(grub_vars['console_num'], serial_console[-1])
        self.assertEqual(grub_vars['console_speed'], default_speed)

        self.cli_delete(base_path)
        self.cli_commit()

        # We moved back to tty as Kernel boot console
        grub_vars = get_grub_vars()
        self.assertEqual(grub_vars['console_type'], 'tty')

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
