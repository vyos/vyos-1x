#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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
from vyos.util import read_file
from vyos.util import process_named_running

PROCESS_NAME = 'igmpproxy'
IGMP_PROXY_CONF = '/etc/igmpproxy.conf'
base_path = ['protocols', 'igmp-proxy']
upstream_if = 'eth1'
downstream_if = 'eth2'

class TestProtocolsIGMPProxy(VyOSUnitTestSHIM.TestCase):
    def setUp(self):
        self.cli_set(['interfaces', 'ethernet', upstream_if, 'address', '172.16.1.1/24'])

    def tearDown(self):
        self.cli_delete(['interfaces', 'ethernet', upstream_if, 'address'])
        self.cli_delete(base_path)
        self.cli_commit()

    def test_igmpproxy(self):
        threshold = '20'
        altnet = '192.0.2.0/24'
        whitelist = '10.0.0.0/8'

        self.cli_set(base_path + ['disable-quickleave'])
        self.cli_set(base_path + ['interface', upstream_if, 'threshold', threshold])
        self.cli_set(base_path + ['interface', upstream_if, 'alt-subnet', altnet])
        self.cli_set(base_path + ['interface', upstream_if, 'whitelist', whitelist])

        # Must define an upstream and at least 1 downstream interface!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['interface', upstream_if, 'role', 'upstream'])

        # Interface does not exist
        self.cli_set(base_path + ['interface', 'eth20', 'role', 'upstream'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['interface', 'eth20'])

        # Only 1 upstream interface allowed
        self.cli_set(base_path + ['interface', downstream_if, 'role', 'upstream'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['interface', downstream_if, 'role', 'downstream'])

        # commit changes
        self.cli_commit()

        # Check generated configuration
        config = read_file(IGMP_PROXY_CONF)
        self.assertIn(f'phyint {upstream_if} upstream ratelimit 0 threshold {threshold}', config)
        self.assertIn(f'altnet {altnet}', config)
        self.assertIn(f'whitelist {whitelist}', config)
        self.assertIn(f'phyint {downstream_if} downstream ratelimit 0 threshold 1', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    unittest.main(verbosity=2)
