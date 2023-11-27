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
    @classmethod
    def setUpClass(cls):
        # call base-classes classmethod
        super(TestProtocolsPIMv6, cls).setUpClass()
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

    def test_pim6_01_mld_simple(self):
        # commit changes
        interfaces = Section.interfaces('ethernet')
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface])

        self.cli_commit()

        # Verify FRR pim6d configuration
        for interface in interfaces:
            config = self.getFRRconfig(f'interface {interface}', daemon=PROCESS_NAME)
            self.assertIn(f'interface {interface}', config)
            self.assertIn(f' ipv6 mld', config)
            self.assertNotIn(f' ipv6 mld version 1', config)

        # Change to MLD version 1
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface, 'mld', 'version', '1'])

        self.cli_commit()

        # Verify FRR pim6d configuration
        for interface in interfaces:
            config = self.getFRRconfig(f'interface {interface}', daemon=PROCESS_NAME)
            self.assertIn(f'interface {interface}', config)
            self.assertIn(f' ipv6 mld', config)
            self.assertIn(f' ipv6 mld version 1', config)

    def test_pim6_02_mld_join(self):
        interfaces = Section.interfaces('ethernet')
        # Use an invalid multicast group address
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface, 'mld', 'join', 'fd00::1234'])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['interface'])

        # Use a valid multicast group address
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface, 'mld', 'join', 'ff18::1234'])

        self.cli_commit()

        # Verify FRR pim6d configuration
        for interface in interfaces:
            config = self.getFRRconfig(f'interface {interface}', daemon=PROCESS_NAME)
            self.assertIn(f'interface {interface}', config)
            self.assertIn(f' ipv6 mld join ff18::1234', config)

        # Join a source-specific multicast group
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface, 'mld', 'join', 'ff38::5678', 'source', '2001:db8::5678'])

        self.cli_commit()

        # Verify FRR pim6d configuration
        for interface in interfaces:
            config = self.getFRRconfig(f'interface {interface}', daemon=PROCESS_NAME)
            self.assertIn(f'interface {interface}', config)
            self.assertIn(f' ipv6 mld join ff38::5678 2001:db8::5678', config)

    def test_pim6_03_basic(self):
        interfaces = Section.interfaces('ethernet')
        join_prune_interval = '123'
        keep_alive_timer = '77'
        packets = '5'
        register_suppress_time = '99'
        dr_priority = '100'
        hello = '50'

        self.cli_set(base_path + ['join-prune-interval', join_prune_interval])
        self.cli_set(base_path + ['keep-alive-timer', keep_alive_timer])
        self.cli_set(base_path + ['packets', packets])
        self.cli_set(base_path + ['register-suppress-time', register_suppress_time])

        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface, 'dr-priority', dr_priority])
            self.cli_set(base_path + ['interface', interface, 'hello', hello])
            self.cli_set(base_path + ['interface', interface, 'no-bsm'])
            self.cli_set(base_path + ['interface', interface, 'no-unicast-bsm'])
            self.cli_set(base_path + ['interface', interface, 'passive'])

        self.cli_commit()

        # Verify FRR pim6d configuration
        config = self.getFRRconfig(daemon=PROCESS_NAME)
        self.assertIn(f'ipv6 pim join-prune-interval {join_prune_interval}', config)
        self.assertIn(f'ipv6 pim keep-alive-timer {keep_alive_timer}', config)
        self.assertIn(f'ipv6 pim packets {packets}', config)
        self.assertIn(f'ipv6 pim register-suppress-time {register_suppress_time}', config)

        for interface in interfaces:
            config = self.getFRRconfig(f'interface {interface}', daemon=PROCESS_NAME)
            self.assertIn(f' ipv6 pim drpriority {dr_priority}', config)
            self.assertIn(f' ipv6 pim hello {hello}', config)
            self.assertIn(f' no ipv6 pim bsm', config)
            self.assertIn(f' no ipv6 pim unicast-bsm', config)
            self.assertIn(f' ipv6 pim passive', config)

if __name__ == '__main__':
    unittest.main(verbosity=2)
