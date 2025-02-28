#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
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
from vyos.utils.process import cmd
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file

PROCESS_NAME = 'hsflowd'
base_path = ['system', 'sflow']
vrf = 'mgmt'

hsflowd_conf = '/run/sflow/hsflowd.conf'

class TestSystemFlowAccounting(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSystemFlowAccounting, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        # after service removal process must no longer run
        self.assertTrue(process_named_running(PROCESS_NAME))

        self.cli_delete(base_path)
        self.cli_delete(['vrf', 'name', vrf])
        self.cli_commit()

        # after service removal process must no longer run
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_sflow(self):
        agent_address = '192.0.2.5'
        agent_interface = 'eth0'
        polling = '24'
        sampling_rate = '128'
        server = '192.0.2.254'
        local_server = '127.0.0.1'
        port = '8192'
        default_port = '6343'
        mon_limit = '50'

        self.cli_set(
            ['interfaces', 'dummy', 'dum0', 'address', f'{agent_address}/24'])
        self.cli_set(base_path + ['agent-address', agent_address])
        self.cli_set(base_path + ['agent-interface', agent_interface])

        # You need to configure at least one interface for sflow
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for interface in Section.interfaces('ethernet'):
            self.cli_set(base_path + ['interface', interface])

        self.cli_set(base_path + ['polling', polling])
        self.cli_set(base_path + ['sampling-rate', sampling_rate])
        self.cli_set(base_path + ['server', server, 'port', port])
        self.cli_set(base_path + ['server', local_server])
        self.cli_set(base_path + ['drop-monitor-limit', mon_limit])

        # commit changes
        self.cli_commit()

        # verify configuration
        hsflowd = read_file(hsflowd_conf)

        self.assertIn(f'polling={polling}', hsflowd)
        self.assertIn(f'sampling={sampling_rate}', hsflowd)
        self.assertIn(f'agentIP={agent_address}', hsflowd)
        self.assertIn(f'agent={agent_interface}', hsflowd)
        self.assertIn(f'collector {{ ip = {server} udpport = {port} }}', hsflowd)
        self.assertIn(f'collector {{ ip = {local_server} udpport = {default_port} }}', hsflowd)
        self.assertIn(f'dropmon {{ limit={mon_limit} start=on sw=on hw=off }}', hsflowd)
        self.assertIn('dbus { }', hsflowd)

        for interface in Section.interfaces('ethernet'):
            self.assertIn(f'pcap {{ dev={interface} }}', hsflowd)

    def test_vrf(self):
        interface = 'eth0'
        server = '192.0.2.1'

        # Check if sFlow service can be bound to given VRF
        self.cli_set(['vrf', 'name', vrf, 'table', '10100'])
        self.cli_set(base_path + ['interface', interface])
        self.cli_set(base_path + ['server', server])
        self.cli_set(base_path + ['vrf', vrf])

        # commit changes
        self.cli_commit()

        # verify configuration
        hsflowd = read_file(hsflowd_conf)
        self.assertIn(f'collector {{ ip = {server} udpport = 6343 }}', hsflowd) # default port
        self.assertIn(f'pcap {{ dev=eth0 }}', hsflowd)

        # Check for process in VRF
        tmp = cmd(f'ip vrf pids {vrf}')
        self.assertIn(PROCESS_NAME, tmp)

if __name__ == '__main__':
    unittest.main(verbosity=2)
