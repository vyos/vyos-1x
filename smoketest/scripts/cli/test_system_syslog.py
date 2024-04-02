#!/usr/bin/env python3
#
# Copyright (C) 2019-2024 VyOS maintainers and contributors
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

from vyos.utils.file import read_file
from vyos.utils.process import process_named_running

PROCESS_NAME = 'rsyslogd'
RSYSLOG_CONF = '/etc/rsyslog.d/00-vyos.conf'

base_path = ['system', 'syslog']

def get_config_value(key):
    tmp = read_file(RSYSLOG_CONF)
    tmp = re.findall(r'\n?{}\s+(.*)'.format(key), tmp)
    return tmp[0]

class TestRSYSLOGService(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestRSYSLOGService, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        # delete testing SYSLOG config
        self.cli_delete(base_path)
        self.cli_commit()

        # Check for running process
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_syslog_basic(self):
        host1 = '198.51.100.1'
        host2 = '192.0.2.1'

        self.cli_set(base_path + ['host', host1, 'port', '999'])
        self.cli_set(base_path + ['host', host1, 'facility', 'all', 'level', 'all'])
        self.cli_set(base_path + ['host', host2, 'facility', 'kern', 'level', 'err'])
        self.cli_set(base_path + ['console', 'facility', 'all', 'level', 'warning'])


        self.cli_commit()
        # verify log level and facilities in config file
        # *.warning /dev/console
        # *.* @198.51.100.1:999
        # kern.err @192.0.2.1:514
        config = [get_config_value('\*.\*'), get_config_value('kern.err'), get_config_value('\*.warning')]
        expected = ['@198.51.100.1:999', '@192.0.2.1:514', '/dev/console']

        for i in range(0,3):
            self.assertIn(expected[i], config[i])
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    unittest.main(verbosity=2)
