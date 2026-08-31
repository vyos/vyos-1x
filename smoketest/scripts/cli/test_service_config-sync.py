#!/usr/bin/env python3
#
# Copyright (C) VyOS Inc.
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

import time
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

HTTPS_PATH = ['service', 'https']
SYNC_PATH = ['service', 'config-sync']

ADDRESS = '127.0.0.1'
KEY = 'id_key'


class TestConfigSyncWithHTTPS(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cli_delete(cls, HTTPS_PATH)
        cls.cli_delete(cls, SYNC_PATH)

    def tearDown(self):
        self.cli_delete(HTTPS_PATH)
        self.cli_delete(SYNC_PATH)

        self.cli_delete(['interfaces', 'dummy'])
        self.cli_delete(['system', 'time-zone'])

        self.cli_commit()
        super().tearDown()

    def _configure_r1_config_sync(self):
        """
        Simulates R1: config-sync client
        """
        self.cli_set(SYNC_PATH + ['mode', 'load'])
        self.cli_set(SYNC_PATH + ['secondary', 'address', ADDRESS])
        self.cli_set(SYNC_PATH + ['secondary', 'key', KEY])
        self.cli_set(SYNC_PATH + ['secondary', 'port', '443'])

        self.cli_set(SYNC_PATH + ['section', 'interfaces', 'dummy'])
        self.cli_set(SYNC_PATH + ['section', 'system', 'time-zone'])

        self.cli_commit()

        # wait to init config-sync service
        time.sleep(1)

    def _configure_r2_https_api(self):
        """
        Simulates R2: HTTPS API endpoint
        """
        self.cli_set(HTTPS_PATH + ['api', 'rest'])
        self.cli_set(HTTPS_PATH + ['api', 'keys', 'id', 'KEY', 'key', KEY])
        self.cli_set(HTTPS_PATH + ['listen-address', '0.0.0.0'])
        self.cli_commit()

    def test_basic(self):
        """
        Validate: basic config-sync configuration (R1 side)
        """

        self._configure_r2_https_api()
        self._configure_r1_config_sync()

        config = self.op_mode(['show', 'configuration', 'commands'])

        self.assertIn("set service config-sync mode 'load'", config)
        self.assertIn(f"set service config-sync secondary address '{ADDRESS}'", config)

    def test_show_diff_candidate_interfaces(self):
        """
        Validate: show configuration secondary sync commands candidate interfaces dummy
        """

        self._configure_r2_https_api()
        self._configure_r1_config_sync()

        # committed config
        self.cli_set(['interfaces', 'dummy', 'dum0', 'address', '192.0.2.1/32'])
        self.cli_commit()

        time.sleep(2)

        # candidate change
        self.cli_set(['interfaces', 'dummy', 'dum0', 'address', '192.0.2.2/32'])

        output = self.op_mode(
            [
                'show',
                'configuration',
                'secondary',
                'sync',
                'commands',
                'candidate',
                'interfaces',
                'dummy',
            ]
        )

        self.assertIsInstance(output, str)
        self.assertIn("set interfaces dummy dum0 address '192.0.2.2/32'", output)

    def test_show_diff_saved_system(self):
        """
        Validate: show configuration secondary sync saved system time-zone
        """

        self._configure_r2_https_api()
        self._configure_r1_config_sync()

        # committed config
        self.cli_set(['system', 'time-zone', 'UTC'])
        self.cli_commit()

        time.sleep(2)

        output = self.op_mode(
            [
                'show',
                'configuration',
                'secondary',
                'sync',
                'saved',
                'system',
                'time-zone',
            ]
        )

        self.assertIsInstance(output, str)
        self.assertIn('[system]\n- time-zone', output)

        output = self.op_mode(['show', 'configuration', 'secondary', 'sync', 'saved'])

        self.assertIsInstance(output, str)
        self.assertIn('[system]\n- time-zone', output)

    def test_show_diff_empty(self):
        """
        No candidate changes -> empty diff
        """

        self._configure_r2_https_api()
        self._configure_r1_config_sync()

        output = self.op_mode(['show', 'configuration', 'secondary', 'sync'])
        self.assertTrue(output.strip() == '' or 'No changes' in output, repr(output))

        output = self.op_mode(
            [
                'show',
                'configuration',
                'secondary',
                'sync',
                'running',
                'interfaces',
                'dummy',
            ]
        )
        self.assertTrue(output.strip() == '' or 'No changes' in output)


if __name__ == '__main__':
    unittest.main(verbosity=5)
