#!/usr/bin/env python3
#
# Copyright (C) 2021-2022 VyOS maintainers and contributors
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

from vyos.template import is_ipv4
from vyos.util import read_file
from vyos.util import get_interface_config
from vyos.validate import is_intf_addr_assigned

base_path = ['system', 'ipv6']

file_forwarding = '/proc/sys/net/ipv6/conf/all/forwarding'
file_disable = '/proc/sys/net/ipv6/conf/all/disable_ipv6'
file_dad = '/proc/sys/net/ipv6/conf/all/accept_dad'
file_multipath = '/proc/sys/net/ipv6/fib_multipath_hash_policy'

class TestSystemIPv6(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_system_ipv6_forwarding(self):
        # Test if IPv6 forwarding can be disabled globally, default is '1'
        # which means forwearding enabled
        self.assertEqual(read_file(file_forwarding), '1')

        self.cli_set(base_path + ['disable-forwarding'])
        self.cli_commit()

        self.assertEqual(read_file(file_forwarding), '0')

    def test_system_ipv6_strict_dad(self):
        # This defaults to 1
        self.assertEqual(read_file(file_dad), '1')

        # Do not assign any IPv6 address on interfaces, this requires a reboot
        # which can not be tested, but we can read the config file :)
        self.cli_set(base_path + ['strict-dad'])
        self.cli_commit()

        # Verify configuration file
        self.assertEqual(read_file(file_dad), '2')

    def test_system_ipv6_multipath(self):
        # This defaults to 0
        self.assertEqual(read_file(file_multipath), '0')

        # Do not assign any IPv6 address on interfaces, this requires a reboot
        # which can not be tested, but we can read the config file :)
        self.cli_set(base_path + ['multipath', 'layer4-hashing'])
        self.cli_commit()

        # Verify configuration file
        self.assertEqual(read_file(file_multipath), '1')

    def test_system_ipv6_neighbor_table_size(self):
        # Maximum number of entries to keep in the ARP cache, the
        # default is 8192

        gc_thresh3 = '/proc/sys/net/ipv6/neigh/default/gc_thresh3'
        gc_thresh2 = '/proc/sys/net/ipv6/neigh/default/gc_thresh2'
        gc_thresh1 = '/proc/sys/net/ipv6/neigh/default/gc_thresh1'
        self.assertEqual(read_file(gc_thresh3), '8192')
        self.assertEqual(read_file(gc_thresh2), '4096')
        self.assertEqual(read_file(gc_thresh1), '1024')

        for size in [1024, 2048, 4096, 8192, 16384, 32768]:
            self.cli_set(base_path + ['neighbor', 'table-size', str(size)])
            self.cli_commit()

            self.assertEqual(read_file(gc_thresh3), str(size))
            self.assertEqual(read_file(gc_thresh2), str(size // 2))
            self.assertEqual(read_file(gc_thresh1), str(size // 8))

if __name__ == '__main__':
    unittest.main(verbosity=2)
