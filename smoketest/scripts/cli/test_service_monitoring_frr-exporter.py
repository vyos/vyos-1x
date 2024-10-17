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
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file

PROCESS_NAME = 'frr_exporter'
base_path = ['service', 'monitoring', 'frr-exporter']
service_file = '/etc/systemd/system/frr_exporter.service'
listen_if = 'dum3421'
listen_ip = '192.0.2.1'


class TestMonitoringFrrExporter(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        # call base-classes classmethod
        super(TestMonitoringFrrExporter, cls).setUpClass()
        # create a test interfaces
        cls.cli_set(
            cls, ['interfaces', 'dummy', listen_if, 'address', listen_ip + '/32']
        )

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['interfaces', 'dummy', listen_if])
        super(TestMonitoringFrrExporter, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_01_basic_config(self):
        self.cli_set(base_path + ['listen-address', listen_ip])

        # commit changes
        self.cli_commit()

        file_content = read_file(service_file)
        self.assertIn(f'{listen_ip}:9342', file_content)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))


if __name__ == '__main__':
    unittest.main(verbosity=2)
