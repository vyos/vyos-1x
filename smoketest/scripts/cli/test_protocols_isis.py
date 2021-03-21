#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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
from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Section
from vyos.util import process_named_running

PROCESS_NAME = 'isisd'
base_path = ['protocols', 'isis']

domain = 'FOOO'
net = '49.0001.1921.6800.1002.00'

class TestProtocolsISIS(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_isis_redistribute(self):
        prefix_list = 'EXPORT-ISIS'
        route_map = 'EXPORT-ISIS'
        rule = '10'
        self.cli_set(['policy', 'prefix-list', prefix_list, 'rule', rule, 'action', 'permit'])
        self.cli_set(['policy', 'prefix-list', prefix_list, 'rule', rule, 'prefix', '203.0.113.0/24'])
        self.cli_set(['policy', 'route-map', route_map, 'rule', rule, 'action', 'permit'])
        self.cli_set(['policy', 'route-map', route_map, 'rule', rule, 'match', 'ip', 'address', 'prefix-list', prefix_list])

        self.cli_set(base_path + ['domain', domain])
        self.cli_set(base_path + ['net', net])
        self.cli_set(base_path + ['redistribute', 'ipv4', 'connected', 'level-2', 'route-map', route_map])

        interfaces = Section.interfaces('ethernet')
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface])

        # Commit all changes
        self.cli_commit()

        # Verify all changes
        tmp = self.getFRRconfig(f'router isis {domain}', end='')
        self.assertIn(f' net {net}', tmp)
        self.assertIn(f' redistribute ipv4 connected level-2 route-map {route_map}', tmp)

        for interface in interfaces:
            tmp = self.getFRRconfig(f'interface {interface}')
            self.assertIn(f' ip router isis {domain}', tmp)

        self.cli_delete(['policy'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
