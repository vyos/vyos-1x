#!/usr/bin/env python3
#
# Copyright (C) 2020 Francois Mertz fireboxled@gmail.com
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
from vyos.util import read_file

base_path = ['system', 'ip']

class TestSystemIP(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())

    def tearDown(self):
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_system_ip_forwarding(self):
        # Test if IPv4 forwarding can be disabled globally, default is '1'
        # which means forwearding enabled
        all_forwarding = '/proc/sys/net/ipv4/conf/all/forwarding'
        self.assertEqual(read_file(all_forwarding), '1')

        self.session.set(base_path + ['disable-forwarding'])
        self.session.commit()

        self.assertEqual(read_file(all_forwarding), '0')

    def test_system_ip_multipath(self):
        # Test IPv4 multipathing options, options default to off -> '0'
        use_neigh = '/proc/sys/net/ipv4/fib_multipath_use_neigh'
        hash_policy = '/proc/sys/net/ipv4/fib_multipath_hash_policy'

        self.assertEqual(read_file(use_neigh), '0')
        self.assertEqual(read_file(hash_policy), '0')

        self.session.set(base_path + ['multipath', 'ignore-unreachable-nexthops'])
        self.session.set(base_path + ['multipath', 'layer4-hashing'])
        self.session.commit()

        self.assertEqual(read_file(use_neigh), '1')
        self.assertEqual(read_file(hash_policy), '1')

    def test_system_ip_arp_table_size(self):
        # Maximum number of entries to keep in the ARP cache, the
        # default is 8k

        gc_thresh3 = '/proc/sys/net/ipv4/neigh/default/gc_thresh3'
        gc_thresh2 = '/proc/sys/net/ipv4/neigh/default/gc_thresh2'
        gc_thresh1 = '/proc/sys/net/ipv4/neigh/default/gc_thresh1'
        self.assertEqual(read_file(gc_thresh3), '8192')
        self.assertEqual(read_file(gc_thresh2), '4096')
        self.assertEqual(read_file(gc_thresh1), '1024')

        for size in [1024, 2048, 4096, 8192, 16384, 32768]:
            self.session.set(base_path + ['arp', 'table-size', str(size)])
            self.session.commit()

            self.assertEqual(read_file(gc_thresh3), str(size))
            self.assertEqual(read_file(gc_thresh2), str(size // 2))
            self.assertEqual(read_file(gc_thresh1), str(size // 8))

if __name__ == '__main__':
    unittest.main(verbosity=2)
