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

import json
import os
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

base_path = ['nat64']
src_path = base_path + ['source']

jool_nat64_config = '/run/jool/instance-100.json'

class TestNAT64(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestNAT64, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()
        self.assertFalse(os.path.exists(jool_nat64_config))

    def test_snat64(self):
        rule = '100'
        translation_rule = '10'
        prefix_v6 = '64:ff9b::/96'
        pool = '192.0.2.10'
        pool_port = '1-65535'

        self.cli_set(src_path + ['rule', rule, 'source', 'prefix', prefix_v6])
        self.cli_set(
            src_path
            + ['rule', rule, 'translation', 'pool', translation_rule, 'address', pool]
        )
        self.cli_set(
            src_path
            + ['rule', rule, 'translation', 'pool', translation_rule, 'port', pool_port]
        )
        self.cli_commit()

        # Load the JSON file
        with open(f'/run/jool/instance-{rule}.json', 'r') as json_file:
            config_data = json.load(json_file)

        # Assertions based on the content of the JSON file
        self.assertEqual(config_data['instance'], f'instance-{rule}')
        self.assertEqual(config_data['framework'], 'netfilter')
        self.assertEqual(config_data['global']['pool6'], prefix_v6)
        self.assertTrue(config_data['global']['manually-enabled'])

        # Check the pool4 entries
        pool4_entries = config_data.get('pool4', [])
        self.assertIsInstance(pool4_entries, list)
        self.assertGreater(len(pool4_entries), 0)

        for entry in pool4_entries:
            self.assertIn('protocol', entry)
            self.assertIn('prefix', entry)
            self.assertIn('port range', entry)

            protocol = entry['protocol']
            prefix = entry['prefix']
            port_range = entry['port range']

            if protocol == 'ICMP':
                self.assertEqual(prefix, pool)
                self.assertEqual(port_range, pool_port)
            elif protocol == 'UDP':
                self.assertEqual(prefix, pool)
                self.assertEqual(port_range, pool_port)
            elif protocol == 'TCP':
                self.assertEqual(prefix, pool)
                self.assertEqual(port_range, pool_port)
            else:
                self.fail(f'Unexpected protocol: {protocol}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
