#!/usr/bin/env python3
#
# Copyright (C) 2020-2024 VyOS maintainers and contributors
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
from vyos.utils.file import read_file

base_path = ['system', 'ip']

class TestSystemIP(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_system_ip_forwarding(self):
        # Test if IPv4 forwarding can be disabled globally, default is '1'
        # which means forwarding enabled
        all_forwarding = '/proc/sys/net/ipv4/conf/all/forwarding'
        self.assertEqual(read_file(all_forwarding), '1')

        self.cli_set(base_path + ['disable-forwarding'])
        self.cli_commit()

        self.assertEqual(read_file(all_forwarding), '0')

    def test_system_ip_multipath(self):
        # Test IPv4 multipathing options, options default to off -> '0'
        use_neigh = '/proc/sys/net/ipv4/fib_multipath_use_neigh'
        hash_policy = '/proc/sys/net/ipv4/fib_multipath_hash_policy'

        self.assertEqual(read_file(use_neigh), '0')
        self.assertEqual(read_file(hash_policy), '0')

        self.cli_set(base_path + ['multipath', 'ignore-unreachable-nexthops'])
        self.cli_set(base_path + ['multipath', 'layer4-hashing'])
        self.cli_commit()

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
            self.cli_set(base_path + ['arp', 'table-size', str(size)])
            self.cli_commit()

            self.assertEqual(read_file(gc_thresh3), str(size))
            self.assertEqual(read_file(gc_thresh2), str(size // 2))
            self.assertEqual(read_file(gc_thresh1), str(size // 8))

    def test_system_ip_protocol_route_map(self):
        protocols = ['any', 'babel', 'bgp', 'connected', 'eigrp', 'isis',
                     'kernel', 'ospf', 'rip', 'static', 'table']

        for protocol in protocols:
            self.cli_set(['policy', 'route-map', f'route-map-{protocol}', 'rule', '10', 'action', 'permit'])
            self.cli_set(base_path + ['protocol', protocol, 'route-map', f'route-map-{protocol}'])

        self.cli_commit()

        # Verify route-map properly applied to FRR
        frrconfig = self.getFRRconfig('ip protocol', end='', daemon='zebra')
        for protocol in protocols:
            self.assertIn(f'ip protocol {protocol} route-map route-map-{protocol}', frrconfig)

        # Delete route-maps
        self.cli_delete(['policy', 'route-map'])
        self.cli_delete(base_path + ['protocol'])

        self.cli_commit()

        # Verify route-map properly applied to FRR
        frrconfig = self.getFRRconfig('ip protocol', end='', daemon='zebra')
        self.assertNotIn(f'ip protocol', frrconfig)

    def test_system_ip_protocol_non_existing_route_map(self):
        non_existing = 'non-existing'
        self.cli_set(base_path + ['protocol', 'static', 'route-map', non_existing])

        # VRF does yet not exist - an error must be thrown
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(['policy', 'route-map', non_existing, 'rule', '10', 'action', 'deny'])

        # Commit again
        self.cli_commit()

    def test_system_ip_nht(self):
        self.cli_set(base_path + ['nht', 'no-resolve-via-default'])
        self.cli_commit()
        # Verify CLI config applied to FRR
        frrconfig = self.getFRRconfig('', end='', daemon='zebra')
        self.assertIn(f'no ip nht resolve-via-default', frrconfig)

        self.cli_delete(base_path + ['nht', 'no-resolve-via-default'])
        self.cli_commit()
        # Verify CLI config removed to FRR
        frrconfig = self.getFRRconfig('', end='', daemon='zebra')
        self.assertNotIn(f'no ip nht resolve-via-default', frrconfig)

if __name__ == '__main__':
    unittest.main(verbosity=2)
