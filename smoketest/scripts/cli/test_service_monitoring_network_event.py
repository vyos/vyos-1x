#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.utils.file import read_json


base_path = ['service', 'monitoring', 'network-event']


def get_logger_config():
    return read_json('/run/vyos-network-event-logger.conf')


class TestMonitoringNetworkEvent(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestMonitoringNetworkEvent, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()
        # always forward to base class
        super().tearDown()

    def test_network_event_log(self):
        expected_config = {
            'event': {
                'route': {},
                'link': {},
                'addr': {},
                'neigh': {},
                'rule': {},
            },
            'queue_size': '10000'
        }

        self.cli_set(base_path + ['event', 'route'])
        self.cli_set(base_path + ['event', 'link'])
        self.cli_set(base_path + ['event', 'addr'])
        self.cli_set(base_path + ['event', 'neigh'])
        self.cli_set(base_path + ['event', 'rule'])
        self.cli_set(base_path + ['queue-size', '10000'])
        self.cli_commit()
        self.assertEqual(expected_config, get_logger_config())


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
