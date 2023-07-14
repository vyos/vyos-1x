#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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
from vyos.utils.file import read_file

PROCESS_NAME = 'dhcrelay'
RELAY_CONF = '/run/dhcp-relay/dhcrelay.conf'
base_path = ['service', 'dhcp-relay']

class TestServiceDHCPRelay(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_relay_default(self):
        max_size = '800'
        hop_count = '20'
        agents_packets = 'append'
        servers = ['192.0.2.1', '192.0.2.2']

        self.cli_set(base_path + ['interface', 'lo'])
        # check validate() - DHCP relay does not support the loopback interface
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['interface', 'lo'])

        # activate DHCP relay on all ethernet interfaces
        for tmp in Section.interfaces("ethernet"):
            self.cli_set(base_path + ['interface', tmp])

        # check validate() - No DHCP relay server(s) configured
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for server in servers:
            self.cli_set(base_path + ['server', server])

        self.cli_set(base_path + ['relay-options', 'max-size', max_size])
        self.cli_set(base_path + ['relay-options', 'hop-count', hop_count])
        self.cli_set(base_path + ['relay-options', 'relay-agents-packets', agents_packets])

        # commit changes
        self.cli_commit()

        # Check configured port
        config = read_file(RELAY_CONF)

        # Test configured relay interfaces
        for tmp in Section.interfaces("ethernet"):
            self.assertIn(f'-i {tmp}', config)

        # Test relay servers
        for server in servers:
            self.assertIn(f' {server}', config)

        # Test max-size
        self.assertIn(f'-A {max_size}', config)
        # Hop count
        self.assertIn(f'-c {hop_count}', config)
        # relay-agents-packets
        self.assertIn(f'-a -m {agents_packets}', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_relay_interfaces(self):
        max_size = '800'
        hop_count = '20'
        agents_packets = 'append'
        servers = ['192.0.2.1', '192.0.2.2']
        listen_iface = 'eth0'
        up_iface = 'eth1'

        self.cli_set(base_path + ['interface', up_iface])
        self.cli_set(base_path + ['listen-interface', listen_iface])
        # check validate() - backward interface plus listen_interface
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['interface'])

        self.cli_set(base_path + ['upstream-interface', up_iface])

        for server in servers:
            self.cli_set(base_path + ['server', server])

        # commit changes
        self.cli_commit()

        # Check configured port
        config = read_file(RELAY_CONF)

        # Test configured relay interfaces
        self.assertIn(f'-id {listen_iface}', config)
        self.assertIn(f'-iu {up_iface}', config)

        # Test relay servers
        for server in servers:
            self.assertIn(f' {server}', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    unittest.main(verbosity=2)

