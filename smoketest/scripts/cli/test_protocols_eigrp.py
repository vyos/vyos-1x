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
from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Section
from vyos.utils.process import process_named_running

PROCESS_NAME = 'eigrpd'
base_path = ['protocols', 'eigrp']
system_as = '200'

class TestProtocolsEIGRP(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProtocolsEIGRP, cls).setUpClass()

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

    def test_basic(self):
        router_id = '5.6.7.8'

        self.cli_set(base_path + ['router-id', router_id])

        # system-as must be set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['system-as', system_as])

        # Commit changes
        self.cli_commit()

        # Validate configuration
        frrconfig = self.getFRRconfig(f'router eigrp {system_as}', daemon=PROCESS_NAME)
        self.assertIn(f'router eigrp {system_as}', frrconfig)
        self.assertIn(f' router-id {router_id}', frrconfig)

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
