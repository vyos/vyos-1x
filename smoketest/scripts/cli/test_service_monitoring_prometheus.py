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
        optional_collectors = ['bgp-l2-vpn', 'pim']
        collector_base = base_path + ['frr-exporter', 'collector']
        self.cli_set(base_path + ['frr-exporter', 'listen-address', listen_ip])

        # commit changes
        self.cli_commit()

        # optional collectors and collector options are opt-in
        file_content = read_file(frr_exporter_service_file)
        self.assertNotIn('--collector.bgp.peer-descriptions', file_content)

        for collector in optional_collectors:
            self.cli_set(collector_base + [collector])

        # BGP collector options
        self.cli_set(collector_base + ['bgp', 'accept-filtered-prefixes'])
        self.cli_set(collector_base + ['bgp', 'advertised-prefixes'])
        self.cli_set(collector_base + ['bgp', 'peer-description', 'plain-text'])
        self.cli_set(collector_base + ['bgp', 'peer-group'])
        self.cli_set(collector_base + ['bgp', 'peer-hostname'])
        self.cli_set(collector_base + ['bgp', 'peer-type'])
        # OSPF collector options
        self.cli_set(collector_base + ['ospf-instance', '1'])
        self.cli_set(collector_base + ['ospf-instance', '2'])
        # Route collector options
        self.cli_set(collector_base + ['detailed-routes'])

        # commit changes
        self.cli_commit()

        file_content = read_file(frr_exporter_service_file)
        self.assertIn(f'{listen_ip}:9342', file_content)
        # bgp6 collector is always enabled
        self.assertIn('--collector.bgp6', file_content)
        for collector in ['bgpl2vpn', 'pim']:
            self.assertIn(f'--collector.{collector}', file_content)
        for flag in [
            '--collector.bgp.accepted-filtered-prefixes',
            '--collector.bgp.advertised-prefixes',
            '--collector.bgp.peer-descriptions',
            '--collector.bgp.peer-descriptions.plain-text',
            '--collector.bgp.peer-groups',
            '--collector.bgp.peer-hostnames',
            '--collector.bgp.peer-types',
            '--collector.ospf.instances=1,2',
            '--collector.route.detailed-routes',
        ]:
            self.assertIn(flag, file_content)

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

    def test_05_blackbox_exporter_with_icmp(self):
        vrf_name = 'bbx'
        be_path = base_path + ['blackbox-exporter']
        self.cli_set(be_path + ['listen-address', listen_ip])
        self.cli_set(
            be_path
            + ['modules', 'icmp', 'name', 'ping4', 'preferred-ip-protocol', 'ipv4']
        )

        self.cli_commit()

        # Verify CAP_NET_RAW is granted when ICMP module is configured (no VRF case)
        file_content = read_file(blackbox_exporter_service_file)
        self.assertIn('AmbientCapabilities=CAP_NET_RAW', file_content)
        self.assertIn('CapabilityBoundingSet=CAP_NET_RAW', file_content)

        # Check for running process
        self.assertTrue(process_named_running(BLACKBOX_EXPORTER_PROCESS_NAME))

        self.cli_delete(be_path + ['modules', 'icmp'])
        self.cli_commit()

        # Verify CAP_NET_RAW is removed when ICMP module is deleted
        file_content = read_file(blackbox_exporter_service_file)
        self.assertNotIn('CAP_NET_RAW', file_content)
        self.assertTrue(process_named_running(BLACKBOX_EXPORTER_PROCESS_NAME))

        # VRF + ICMP should use setpriv with net_raw capabilities
        self.cli_set(['vrf', 'name', vrf_name, 'table', '1111'])
        # Move the listen interface into the VRF so the exporter can bind
        self.cli_set(['interfaces', 'dummy', listen_if, 'vrf', vrf_name])
        self.cli_set(be_path + ['vrf', vrf_name])
        self.cli_set(
            be_path
            + ['modules', 'icmp', 'name', 'ping4', 'preferred-ip-protocol', 'ipv4']
        )
        self.cli_commit()

        # Verify VRF uses setpriv instead of systemd capabilities
        file_content = read_file(blackbox_exporter_service_file)
        self.assertIn('setpriv', file_content)
        self.assertIn('--ambient-caps=+net_raw', file_content)
        self.assertIn('--inh-caps=+net_raw', file_content)
        self.assertNotIn('AmbientCapabilities=CAP_NET_RAW', file_content)

        # Ensure the exporter actually started under setpriv in the VRF
        self.assertTrue(process_named_running(BLACKBOX_EXPORTER_PROCESS_NAME))

        # Cleanup VRF
        self.cli_delete(['interfaces', 'dummy', listen_if, 'vrf'])
        self.cli_delete(['vrf', 'name', vrf_name])


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
