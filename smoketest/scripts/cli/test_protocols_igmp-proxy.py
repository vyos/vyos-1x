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

import os
import unittest

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import read_file
from vyos.util import process_named_running

PROCESS_NAME = 'igmpproxy'
IGMP_PROXY_CONF = '/etc/igmpproxy.conf'
base_path = ['protocols', 'igmp-proxy']
upstream_if = 'eth1'
downstream_if = 'eth2'

class TestProtocolsIGMPProxy(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        self.session.set(['interfaces', 'ethernet', upstream_if, 'address', '172.16.1.1/24'])

    def tearDown(self):
        self.session.delete(['interfaces', 'ethernet', upstream_if, 'address'])
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_igmpproxy(self):
        threshold = '20'
        altnet = '192.0.2.0/24'
        whitelist = '10.0.0.0/8'

        self.session.set(base_path + ['disable-quickleave'])
        self.session.set(base_path + ['interface', upstream_if, 'threshold', threshold])
        self.session.set(base_path + ['interface', upstream_if, 'alt-subnet', altnet])
        self.session.set(base_path + ['interface', upstream_if, 'whitelist', whitelist])

        # Must define an upstream and at least 1 downstream interface!
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(base_path + ['interface', upstream_if, 'role', 'upstream'])

        # Interface does not exist
        self.session.set(base_path + ['interface', 'eth20', 'role', 'upstream'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(base_path + ['interface', 'eth20'])

        # Only 1 upstream interface allowed
        self.session.set(base_path + ['interface', downstream_if, 'role', 'upstream'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(base_path + ['interface', downstream_if, 'role', 'downstream'])

        # commit changes
        self.session.commit()

        # Check generated configuration
        config = read_file(IGMP_PROXY_CONF)
        self.assertIn(f'phyint {upstream_if} upstream ratelimit 0 threshold {threshold}', config)
        self.assertIn(f'altnet {altnet}', config)
        self.assertIn(f'whitelist {whitelist}', config)
        self.assertIn(f'phyint {downstream_if} downstream ratelimit 0 threshold 1', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    unittest.main()
