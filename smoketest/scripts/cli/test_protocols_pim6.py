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

import unittest

from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Section
from vyos.utils.process import process_named_running

PROCESS_NAME = 'pim6d'
base_path = ['protocols', 'pim6']


class TestProtocolsPIMv6(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))
        self.cli_delete(base_path)
        self.cli_commit()

    def test_pim6_01_mld_simple(self):
        # commit changes
        interfaces = Section.interfaces('ethernet')

        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface])

        self.cli_commit()

        # Verify FRR pim6d configuration
        for interface in interfaces:
            config = self.getFRRconfig(
                f'interface {interface}', daemon=PROCESS_NAME)
            self.assertIn(f'interface {interface}', config)
            self.assertIn(f' ipv6 mld', config)
            self.assertNotIn(f' ipv6 mld version 1', config)

        # Change to MLD version 1
        for interface in interfaces:
            self.cli_set(base_path + ['interface',
                         interface, 'mld', 'version', '1'])

        self.cli_commit()

        # Verify FRR pim6d configuration
        for interface in interfaces:
            config = self.getFRRconfig(
                f'interface {interface}', daemon=PROCESS_NAME)
            self.assertIn(f'interface {interface}', config)
            self.assertIn(f' ipv6 mld', config)
            self.assertIn(f' ipv6 mld version 1', config)

    def test_pim6_02_mld_join(self):
        # commit changes
        interfaces = Section.interfaces('ethernet')

        # Use an invalid multiple group address
        for interface in interfaces:
            self.cli_set(base_path + ['interface',
                         interface, 'mld', 'join', 'fd00::1234'])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['interface'])

        # Use a valid multiple group address
        for interface in interfaces:
            self.cli_set(base_path + ['interface',
                         interface, 'mld', 'join', 'ff18::1234'])

        self.cli_commit()

        # Verify FRR pim6d configuration
        for interface in interfaces:
            config = self.getFRRconfig(
                f'interface {interface}', daemon=PROCESS_NAME)
            self.assertIn(f'interface {interface}', config)
            self.assertIn(f' ipv6 mld join ff18::1234', config)

        # Join a source-specific multicast group
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface,
                         'mld', 'join', 'ff38::5678', 'source', '2001:db8::5678'])

        self.cli_commit()

        # Verify FRR pim6d configuration
        for interface in interfaces:
            config = self.getFRRconfig(
                f'interface {interface}', daemon=PROCESS_NAME)
            self.assertIn(f'interface {interface}', config)
            self.assertIn(f' ipv6 mld join ff38::5678 2001:db8::5678', config)


if __name__ == '__main__':
    unittest.main(verbosity=2)
