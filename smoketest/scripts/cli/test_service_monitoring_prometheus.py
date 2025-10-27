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

import os
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file

NODE_EXPORTER_PROCESS_NAME = 'node_exporter'
FRR_EXPORTER_PROCESS_NAME = 'frr_exporter'
BLACKBOX_EXPORTER_PROCESS_NAME = 'blackbox_exporter'

base_path = ['service', 'monitoring', 'prometheus']
listen_if = 'dum3421'
listen_ip = '192.0.2.1'
node_exporter_service_file = '/etc/systemd/system/node_exporter.service'
frr_exporter_service_file = '/etc/systemd/system/frr_exporter.service'
blackbox_exporter_service_file = '/etc/systemd/system/blackbox_exporter.service'


class TestMonitoringPrometheus(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        # call base-classes classmethod
        super(TestMonitoringPrometheus, cls).setUpClass()
        # create a test interfaces
        cls.cli_set(
            cls, ['interfaces', 'dummy', listen_if, 'address', listen_ip + '/32']
        )

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['interfaces', 'dummy', listen_if])
        super(TestMonitoringPrometheus, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()
        self.assertFalse(process_named_running(NODE_EXPORTER_PROCESS_NAME))
        self.assertFalse(process_named_running(FRR_EXPORTER_PROCESS_NAME))
        # always forward to base class
        super().tearDown()

    def test_01_node_exporter(self):
        self.cli_set(base_path + ['node-exporter', 'listen-address', listen_ip])
        self.cli_set(base_path + ['node-exporter', 'collectors', 'textfile'])

        # commit changes
        self.cli_commit()

        file_content = read_file(node_exporter_service_file)
        self.assertIn(f'{listen_ip}:9100', file_content)

        self.assertTrue(os.path.isdir('/run/node_exporter/collector'))
        self.assertIn(
            '--collector.textfile.directory=/run/node_exporter/collector', file_content
        )

        # Check for running process
        self.assertTrue(process_named_running(NODE_EXPORTER_PROCESS_NAME))

    def test_02_frr_exporter(self):
        self.cli_set(base_path + ['frr-exporter', 'listen-address', listen_ip])

        # commit changes
        self.cli_commit()

        file_content = read_file(frr_exporter_service_file)
        self.assertIn(f'{listen_ip}:9342', file_content)

        # Check for running process
        self.assertTrue(process_named_running(FRR_EXPORTER_PROCESS_NAME))

    def test_03_blackbox_exporter(self):
        self.cli_set(base_path + ['blackbox-exporter', 'listen-address', listen_ip])

        # commit changes
        self.cli_commit()

        file_content = read_file(blackbox_exporter_service_file)
        self.assertIn(f'{listen_ip}:9115', file_content)

        # Check for running process
        self.assertTrue(process_named_running(BLACKBOX_EXPORTER_PROCESS_NAME))

    def test_04_blackbox_exporter_with_config(self):
        self.cli_set(base_path + ['blackbox-exporter', 'listen-address', listen_ip])
        self.cli_set(
            base_path
            + [
                'blackbox-exporter',
                'modules',
                'dns',
                'name',
                'dns_ip4',
                'preferred-ip-protocol',
                'ipv4',
            ]
        )
        self.cli_set(
            base_path
            + [
                'blackbox-exporter',
                'modules',
                'dns',
                'name',
                'dns_ip4',
                'query-name',
                'vyos.io',
            ]
        )
        self.cli_set(
            base_path
            + [
                'blackbox-exporter',
                'modules',
                'dns',
                'name',
                'dns_ip4',
                'query-type',
                'A',
            ]
        )
        self.cli_set(
            base_path
            + [
                'blackbox-exporter',
                'modules',
                'icmp',
                'name',
                'icmp_ip6',
                'preferred-ip-protocol',
                'ipv6',
            ]
        )

        # commit changes
        self.cli_commit()

        file_content = read_file(blackbox_exporter_service_file)
        self.assertIn(f'{listen_ip}:9115', file_content)

        # Check for running process
        self.assertTrue(process_named_running(BLACKBOX_EXPORTER_PROCESS_NAME))


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
