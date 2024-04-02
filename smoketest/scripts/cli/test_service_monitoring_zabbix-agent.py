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
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file


PROCESS_NAME = 'zabbix_agent2'
ZABBIX_AGENT_CONF = '/run/zabbix/zabbix-agent2.conf'
base_path = ['service', 'monitoring', 'zabbix-agent']


class TestZabbixAgent(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        self.cli_delete(base_path)
        self.cli_commit()

        # Process must be terminated after deleting the config
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_01_zabbix_agent(self):
        directory = '/tmp'
        buffer_send = '8'
        buffer_size = '120'
        log_level = {'warning': '3'}
        log_size = '1'
        servers = ['192.0.2.1', '2001:db8::1']
        servers_active = {'192.0.2.5': {'port': '10051'}, '2001:db8::123': {'port': '10052'}}
        port = '10050'
        timeout = '5'
        listen_ip = '0.0.0.0'
        hostname = 'r-vyos'

        self.cli_set(base_path + ['directory', directory])
        self.cli_set(base_path + ['limits', 'buffer-flush-interval', buffer_send])
        self.cli_set(base_path + ['limits', 'buffer-size', buffer_size])
        self.cli_set(base_path + ['log', 'debug-level', next(iter(log_level))])
        self.cli_set(base_path + ['log', 'size', log_size])
        for server in servers:
            self.cli_set(base_path + ['server', server])
        for server_active, server_config in servers_active.items():
            self.cli_set(base_path + ['server-active', server_active, 'port', server_config['port']])
        self.cli_set(base_path + ['timeout', timeout])
        self.cli_set(base_path + ['host-name', hostname])

        # commit changes
        self.cli_commit()

        config = read_file(ZABBIX_AGENT_CONF)

        self.assertIn(f'LogFileSize={log_size}', config)
        self.assertIn(f'DebugLevel={log_level.get("warning")}', config)

        self.assertIn(f'Server={",".join(sorted(servers))}', config)
        tmp = 'ServerActive=192.0.2.5:10051,[2001:db8::123]:10052'
        self.assertIn(tmp, config)

        self.assertIn(f'ListenPort={port}', config)
        self.assertIn(f'ListenIP={listen_ip}', config)
        self.assertIn(f'BufferSend={buffer_send}', config)
        self.assertIn(f'BufferSize={buffer_size}', config)
        self.assertIn(f'Include={directory}/*.conf', config)
        self.assertIn(f'Timeout={timeout}', config)
        self.assertIn(f'Hostname={hostname}', config)


if __name__ == '__main__':
    unittest.main(verbosity=2)
