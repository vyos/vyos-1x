#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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

from vyos.configsession import ConfigSessionError
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file

PROCESS_NAME = 'fastnetmon'
FASTNETMON_CONF = '/run/fastnetmon/fastnetmon.conf'
NETWORKS_CONF = '/run/fastnetmon/networks_list'
EXCLUDED_NETWORKS_CONF = '/run/fastnetmon/excluded_networks_list'
base_path = ['service', 'ids', 'ddos-protection']

class TestServiceIDS(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestServiceIDS, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        # delete test config
        self.cli_delete(base_path)
        self.cli_commit()

        self.assertFalse(os.path.exists(FASTNETMON_CONF))
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_fastnetmon(self):
        networks = ['10.0.0.0/24', '10.5.5.0/24', '2001:db8:10::/64', '2001:db8:20::/64']
        excluded_networks = ['10.0.0.1/32', '2001:db8:10::1/128']
        interfaces = ['eth0', 'eth1']
        fps = '3500'
        mbps = '300'
        pps = '60000'

        self.cli_set(base_path + ['mode', 'mirror'])
        # Required network!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for tmp in networks:
            self.cli_set(base_path + ['network', tmp])

        # optional excluded-network!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for tmp in excluded_networks:
            self.cli_set(base_path + ['excluded-network', tmp])

        # Required interface(s)!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for tmp in interfaces:
            self.cli_set(base_path + ['listen-interface', tmp])

        self.cli_set(base_path + ['direction', 'in'])
        self.cli_set(base_path + ['threshold', 'general', 'fps', fps])
        self.cli_set(base_path + ['threshold', 'general', 'pps', pps])
        self.cli_set(base_path + ['threshold', 'general', 'mbps', mbps])

        # commit changes
        self.cli_commit()

        # Check configured port
        config = read_file(FASTNETMON_CONF)
        self.assertIn(f'mirror_afpacket = on', config)
        self.assertIn(f'process_incoming_traffic = on', config)
        self.assertIn(f'process_outgoing_traffic = off', config)
        self.assertIn(f'ban_for_flows = on', config)
        self.assertIn(f'threshold_flows = {fps}', config)
        self.assertIn(f'ban_for_bandwidth = on', config)
        self.assertIn(f'threshold_mbps = {mbps}', config)
        self.assertIn(f'ban_for_pps = on', config)
        self.assertIn(f'threshold_pps = {pps}', config)
        # default
        self.assertIn(f'enable_ban = on', config)
        self.assertIn(f'enable_ban_ipv6 = on', config)
        self.assertIn(f'ban_time = 1900', config)

        tmp = ','.join(interfaces)
        self.assertIn(f'interfaces = {tmp}', config)


        network_config = read_file(NETWORKS_CONF)
        for tmp in networks:
            self.assertIn(f'{tmp}', network_config)

        excluded_network_config = read_file(EXCLUDED_NETWORKS_CONF)
        for tmp in excluded_networks:
            self.assertIn(f'{tmp}', excluded_network_config)

if __name__ == '__main__':
    unittest.main(verbosity=2)
