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

from vyos.configsession import ConfigSessionError
from vyos.utils.system import sysctl_read
from vyos.xml_ref import default_value

base_path = ['system', 'ipv6']

class TestSystemIPv6(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSystemIPv6, cls).setUpClass()
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_system_ipv6_forwarding(self):
        # Test if IPv6 forwarding can be disabled globally, default is '1'
        # which means forwearding enabled
        self.assertEqual(sysctl_read('net.ipv6.conf.all.forwarding'), '1')

        self.cli_set(base_path + ['disable-forwarding'])
        self.cli_commit()
        self.assertEqual(sysctl_read('net.ipv6.conf.all.forwarding'), '0')
        frrconfig = self.getFRRconfig('', end='')
        self.assertIn('no ipv6 forwarding', frrconfig)

        self.cli_delete(base_path + ['disable-forwarding'])
        self.cli_commit()
        self.assertEqual(sysctl_read('net.ipv6.conf.all.forwarding'), '1')
        frrconfig = self.getFRRconfig('', end='')
        self.assertNotIn('no ipv6 forwarding', frrconfig)

    def test_system_ipv6_strict_dad(self):
        # This defaults to 1
        self.assertEqual(sysctl_read('net.ipv6.conf.all.accept_dad'), '1')

        # Do not assign any IPv6 address on interfaces, this requires a reboot
        # which can not be tested, but we can read the config file :)
        self.cli_set(base_path + ['strict-dad'])
        self.cli_commit()

        # Verify configuration file
        self.assertEqual(sysctl_read('net.ipv6.conf.all.accept_dad'), '2')

    def test_system_ipv6_multipath(self):
        # This defaults to 0
        self.assertEqual(sysctl_read('net.ipv6.fib_multipath_hash_policy'), '0')

        # Do not assign any IPv6 address on interfaces, this requires a reboot
        # which can not be tested, but we can read the config file :)
        self.cli_set(base_path + ['multipath', 'layer4-hashing'])
        self.cli_commit()

        # Verify configuration file
        self.assertEqual(sysctl_read('net.ipv6.fib_multipath_hash_policy'), '1')

    def test_system_ipv6_neighbor_table_size(self):
        # Maximum number of entries to keep in the ARP cache, the
        # default is 8192
        cli_default = int(default_value(base_path + ['neighbor', 'table-size']))

        def _verify_gc_thres(table_size):
            self.assertEqual(sysctl_read('net.ipv6.neigh.default.gc_thresh3'), str(table_size))
            self.assertEqual(sysctl_read('net.ipv6.neigh.default.gc_thresh2'), str(table_size // 2))
            self.assertEqual(sysctl_read('net.ipv6.neigh.default.gc_thresh1'), str(table_size // 8))

        _verify_gc_thres(cli_default)

        for size in [1024, 2048, 4096, 8192, 16384, 32768]:
            self.cli_set(base_path + ['neighbor', 'table-size', str(size)])
            self.cli_commit()
            _verify_gc_thres(size)

    def test_system_ipv6_protocol_route_map(self):
        protocols = ['any', 'babel', 'bgp', 'connected', 'isis',
                     'kernel', 'ospfv3', 'ripng', 'static', 'table']

        for protocol in protocols:
            route_map = 'route-map-' + protocol.replace('ospfv3', 'ospf6')

            self.cli_set(['policy', 'route-map', route_map, 'rule', '10', 'action', 'permit'])
            self.cli_set(base_path + ['protocol', protocol, 'route-map', route_map])

        self.cli_commit()

        # Verify route-map properly applied to FRR
        frrconfig = self.getFRRconfig('ipv6 protocol', end='')
        for protocol in protocols:
            # VyOS and FRR use a different name for OSPFv3 (IPv6)
            if protocol == 'ospfv3':
                protocol = 'ospf6'
            self.assertIn(f'ipv6 protocol {protocol} route-map route-map-{protocol}', frrconfig)

        # Delete route-maps
        self.cli_delete(['policy', 'route-map'])
        self.cli_delete(base_path + ['protocol'])

        self.cli_commit()

        # Verify route-map properly applied to FRR
        frrconfig = self.getFRRconfig('ipv6 protocol', end='')
        self.assertNotIn(f'ipv6 protocol', frrconfig)

    def test_system_ipv6_protocol_non_existing_route_map(self):
        non_existing = 'non-existing6'
        self.cli_set(base_path + ['protocol', 'static', 'route-map', non_existing])

        # VRF does yet not exist - an error must be thrown
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(['policy', 'route-map', non_existing, 'rule', '10', 'action', 'deny'])

        # Commit again
        self.cli_commit()

    def test_system_ipv6_nht(self):
        self.cli_set(base_path + ['nht', 'no-resolve-via-default'])
        self.cli_commit()
        # Verify CLI config applied to FRR
        frrconfig = self.getFRRconfig('', end='')
        self.assertIn(f'no ipv6 nht resolve-via-default', frrconfig)

        self.cli_delete(base_path + ['nht', 'no-resolve-via-default'])
        self.cli_commit()
        # Verify CLI config removed to FRR
        frrconfig = self.getFRRconfig('', end='')
        self.assertNotIn(f'no ipv6 nht resolve-via-default', frrconfig)

if __name__ == '__main__':
    unittest.main(verbosity=2)
