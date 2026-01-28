#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.frrender import zebra_daemon
from vyos.utils.process import process_named_running

base_path = ['protocols', 'traffic-engineering']

dummy_if1 = 'dum2191'
dummy_if2 = 'dum2192'


class TestProtocolsTrafficEngineering(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        # call base-classes classmethod
        super(TestProtocolsTrafficEngineering, cls).setUpClass()
        # Retrieve FRR daemon PID - it is not allowed to crash, thus PID must remain the same
        cls.daemon_pid = process_named_running(zebra_daemon)
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

        cls.cli_set(cls, ['interfaces', 'dummy', dummy_if1])
        cls.cli_set(cls, ['interfaces', 'dummy', dummy_if2])
        cls.cli_commit(cls)

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['interfaces', 'dummy', dummy_if2])
        cls.cli_delete(cls, ['interfaces', 'dummy', dummy_if1])
        cls.cli_commit(cls)

        super(TestProtocolsTrafficEngineering, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        # check process health and continuity
        self.assertEqual(self.daemon_pid, process_named_running(zebra_daemon))
        # always forward to base class
        super().tearDown()

    def test_te_normal(self):
        self.cli_set(base_path + ['admin-group', 'cyan', 'bit-position', '1'])
        self.cli_set(base_path + ['admin-group', 'magenta', 'bit-position', '3'])

        self.cli_set(base_path + ['interface', dummy_if1, 'admin-group', 'magenta'])
        self.cli_set(base_path + ['interface', dummy_if1, 'max-bandwidth', '1024'])
        self.cli_set(
            base_path + ['interface', dummy_if1, 'max-reservable-bandwidth', '2048']
        )
        self.cli_set(base_path + ['interface', dummy_if1, 'metric', '74837'])

        self.cli_set(base_path + ['interface', dummy_if2, 'admin-group', 'cyan'])
        self.cli_set(base_path + ['interface', dummy_if2, 'admin-group', 'magenta'])

        self.cli_commit()

        frrconfig = self.getFRRconfig(f'^interface {dummy_if1}', stop_section='^exit')
        self.assertIn('link-params', frrconfig)
        self.assertIn('metric 74837', frrconfig)
        self.assertIn('admin-grp 0x8', frrconfig)
        self.assertIn('max-bw 1.34218e+08', frrconfig)
        self.assertIn('max-rsv-bw 2.68435e+08', frrconfig)
        self.assertIn('unrsv-bw 0 2.68435e+08', frrconfig)
        self.assertIn('unrsv-bw 1 2.68435e+08', frrconfig)
        self.assertIn('unrsv-bw 2 2.68435e+08', frrconfig)
        self.assertIn('unrsv-bw 3 2.68435e+08', frrconfig)
        self.assertIn('unrsv-bw 4 2.68435e+08', frrconfig)
        self.assertIn('unrsv-bw 5 2.68435e+08', frrconfig)
        self.assertIn('unrsv-bw 6 2.68435e+08', frrconfig)
        self.assertIn('unrsv-bw 7 2.68435e+08', frrconfig)

        frrconfig = self.getFRRconfig(f'^interface {dummy_if2}', stop_section='^exit')
        self.assertIn('link-params', frrconfig)
        self.assertIn('admin-grp 0xa', frrconfig)

    def test_te_verify(self):
        self.cli_set(base_path + ['interface', dummy_if1, 'admin-group', 'cyan'])

        # Unknown group
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['admin-group', 'cyan', 'bit-position', '0'])
        self.cli_set(base_path + ['admin-group', 'magenta', 'bit-position', '4'])

        # Now group is known
        self.cli_commit()

        self.cli_set(base_path + ['admin-group', 'red', 'bit-position', '4'])

        # Same bit position as other group
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['admin-group', 'red', 'bit-position', '2'])
        # Now should be ok
        self.cli_commit()


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
