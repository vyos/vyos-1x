#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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

from vyos.utils.process import process_named_running
from vyos.utils.file import read_file

PROCESS_NAME = 'telegraf'
TELEGRAF_CONF = '/run/telegraf/telegraf.conf'
base_path = ['service', 'monitoring', 'telegraf']
org = 'log@in.local'
token = 'GuRJc12tIzfjnYdKRAIYbxdWd2aTpOT9PVYNddzDnFV4HkAcD7u7-kndTFXjGuXzJN6TTxmrvPODB4mnFcseDV=='
port = '8888'
url = 'https://foo.local'
bucket = 'main'
inputs = ['cpu', 'disk', 'mem', 'net', 'system', 'kernel', 'interrupts', 'syslog']

class TestMonitoringTelegraf(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        self.cli_delete(base_path)
        self.cli_commit()

        # Check for not longer running process
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_01_basic_config(self):
        self.cli_set(base_path + ['influxdb', 'authentication', 'organization', org])
        self.cli_set(base_path + ['influxdb', 'authentication', 'token', token])
        self.cli_set(base_path + ['influxdb', 'port', port])
        self.cli_set(base_path + ['influxdb', 'url', url])

        # commit changes
        self.cli_commit()

        config = read_file(TELEGRAF_CONF)

        # Check telegraf config
        self.assertIn(f'organization = "{org}"', config)
        self.assertIn(f'  token = "$INFLUX_TOKEN"', config)
        self.assertIn(f'urls = ["{url}:{port}"]', config)
        self.assertIn(f'bucket = "{bucket}"', config)
        self.assertIn(f'[[inputs.exec]]', config)

        for input in inputs:
            self.assertIn(input, config)

    def test_02_loki(self):
        label = 'r123'
        loki_url = 'http://localhost'
        port = '3100'
        loki_username = 'VyOS'
        loki_password = 'PassW0Rd_VyOS'

        self.cli_set(base_path + ['loki', 'url', loki_url])
        self.cli_set(base_path + ['loki', 'port', port])
        self.cli_set(base_path + ['loki', 'metric-name-label', label])

        self.cli_set(base_path + ['loki', 'authentication', 'username', loki_username])
        # password not set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['loki', 'authentication', 'password', loki_password])

        # commit changes
        self.cli_commit()

        config = read_file(TELEGRAF_CONF)
        self.assertIn(f'[[outputs.loki]]', config)
        self.assertIn(f'domain = "{loki_url}:{port}"', config)
        self.assertIn(f'metric_name_label = "{label}"', config)
        self.assertIn(f'username = "{loki_username}"', config)
        self.assertIn(f'password = "{loki_password}"', config)


if __name__ == '__main__':
    unittest.main(verbosity=2)
