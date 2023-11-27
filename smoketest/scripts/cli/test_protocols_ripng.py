#!/usr/bin/env python3
#
# Copyright (C) 2021-2023 VyOS maintainers and contributors
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

from vyos.ifconfig import Section
from vyos.utils.process import process_named_running

PROCESS_NAME = 'ripngd'
acl_in = '198'
acl_out = '199'
prefix_list_in = 'foo-prefix'
prefix_list_out = 'bar-prefix'
route_map = 'FooBar123'

base_path = ['protocols', 'ripng']

class TestProtocolsRIPng(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        # call base-classes classmethod
        super(TestProtocolsRIPng, cls).setUpClass()
        # Retrieve FRR daemon PID - it is not allowed to crash, thus PID must remain the same
        cls.daemon_pid = process_named_running(PROCESS_NAME)
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

        cls.cli_set(cls, ['policy', 'access-list6', acl_in, 'rule', '10', 'action', 'permit'])
        cls.cli_set(cls, ['policy', 'access-list6', acl_in, 'rule', '10', 'source', 'any'])
        cls.cli_set(cls, ['policy', 'access-list6', acl_out, 'rule', '20', 'action', 'deny'])
        cls.cli_set(cls, ['policy', 'access-list6', acl_out, 'rule', '20', 'source', 'any'])
        cls.cli_set(cls, ['policy', 'prefix-list6', prefix_list_in, 'rule', '100', 'action', 'permit'])
        cls.cli_set(cls, ['policy', 'prefix-list6', prefix_list_in, 'rule', '100', 'prefix', '2001:db8::/32'])
        cls.cli_set(cls, ['policy', 'prefix-list6', prefix_list_out, 'rule', '200', 'action', 'deny'])
        cls.cli_set(cls, ['policy', 'prefix-list6', prefix_list_out, 'rule', '200', 'prefix', '2001:db8::/32'])
        cls.cli_set(cls, ['policy', 'route-map', route_map, 'rule', '10', 'action', 'permit'])

    @classmethod
    def tearDownClass(cls):
        # call base-classes classmethod
        super(TestProtocolsRIPng, cls).tearDownClass()

        cls.cli_delete(cls, ['policy', 'access-list6', acl_in])
        cls.cli_delete(cls, ['policy', 'access-list6', acl_out])
        cls.cli_delete(cls, ['policy', 'prefix-list6', prefix_list_in])
        cls.cli_delete(cls, ['policy', 'prefix-list6', prefix_list_out])
        cls.cli_delete(cls, ['policy', 'route-map', route_map])

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        # check process health and continuity
        self.assertEqual(self.daemon_pid, process_named_running(PROCESS_NAME))

    def test_ripng_01_parameters(self):
        metric = '8'
        interfaces = Section.interfaces('ethernet')
        aggregates = ['2001:db8:1000::/48', '2001:db8:2000::/48', '2001:db8:3000::/48']
        networks = ['2001:db8:1000::/64', '2001:db8:1001::/64', '2001:db8:2000::/64', '2001:db8:2001::/64']
        redistribute = ['bgp', 'connected', 'kernel', 'ospfv3', 'static']
        timer_garbage = '888'
        timer_timeout = '1000'
        timer_update = '90'

        self.cli_set(base_path + ['default-information', 'originate'])
        self.cli_set(base_path + ['default-metric', metric])
        self.cli_set(base_path + ['distribute-list', 'access-list', 'in', acl_in])
        self.cli_set(base_path + ['distribute-list', 'access-list', 'out', acl_out])
        self.cli_set(base_path + ['distribute-list', 'prefix-list', 'in', prefix_list_in])
        self.cli_set(base_path + ['distribute-list', 'prefix-list', 'out', prefix_list_out])
        self.cli_set(base_path + ['passive-interface', 'default'])
        self.cli_set(base_path + ['timers', 'garbage-collection', timer_garbage])
        self.cli_set(base_path + ['timers', 'timeout', timer_timeout])
        self.cli_set(base_path + ['timers', 'update', timer_update])
        for aggregate in aggregates:
            self.cli_set(base_path + ['aggregate-address', aggregate])

        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface])
            self.cli_set(base_path + ['distribute-list', 'interface', interface, 'access-list', 'in', acl_in])
            self.cli_set(base_path + ['distribute-list', 'interface', interface, 'access-list', 'out', acl_out])
            self.cli_set(base_path + ['distribute-list', 'interface', interface, 'prefix-list', 'in', prefix_list_in])
            self.cli_set(base_path + ['distribute-list', 'interface', interface, 'prefix-list', 'out', prefix_list_out])
        for network in networks:
            self.cli_set(base_path + ['network', network])
            self.cli_set(base_path + ['route', network])
        for proto in redistribute:
            self.cli_set(base_path + ['redistribute', proto, 'metric', metric])
            self.cli_set(base_path + ['redistribute', proto, 'route-map', route_map])


        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ripng')
        self.assertIn(f'router ripng', frrconfig)
        self.assertIn(f' default-information originate', frrconfig)
        self.assertIn(f' default-metric {metric}', frrconfig)
        self.assertIn(f' ipv6 distribute-list {acl_in} in', frrconfig)
        self.assertIn(f' ipv6 distribute-list {acl_out} out', frrconfig)
        self.assertIn(f' ipv6 distribute-list prefix {prefix_list_in} in', frrconfig)
        self.assertIn(f' ipv6 distribute-list prefix {prefix_list_out} out', frrconfig)
        self.assertIn(f' passive-interface default', frrconfig)
        self.assertIn(f' timers basic {timer_update} {timer_timeout} {timer_garbage}', frrconfig)
        for aggregate in aggregates:
            self.assertIn(f' aggregate-address {aggregate}', frrconfig)
        for interface in interfaces:
            self.assertIn(f' network {interface}', frrconfig)
            self.assertIn(f' ipv6 distribute-list {acl_in} in {interface}', frrconfig)
            self.assertIn(f' ipv6 distribute-list {acl_out} out {interface}', frrconfig)
            self.assertIn(f' ipv6 distribute-list prefix {prefix_list_in} in {interface}', frrconfig)
            self.assertIn(f' ipv6 distribute-list prefix {prefix_list_out} out {interface}', frrconfig)
        for network in networks:
            self.assertIn(f' network {network}', frrconfig)
            self.assertIn(f' route {network}', frrconfig)
        for proto in redistribute:
            if proto == 'ospfv3':
                proto = 'ospf6'
            self.assertIn(f' redistribute {proto} metric {metric} route-map {route_map}', frrconfig)

    def test_ripng_02_zebra_route_map(self):
        # Implemented because of T3328
        self.cli_set(base_path + ['route-map', route_map])
        # commit changes
        self.cli_commit()

        # Verify FRR configuration
        zebra_route_map = f'ipv6 protocol ripng route-map {route_map}'
        frrconfig = self.getFRRconfig(zebra_route_map)
        self.assertIn(zebra_route_map, frrconfig)

        # Remove the route-map again
        self.cli_delete(base_path + ['route-map'])
        # commit changes
        self.cli_commit()

        # Verify FRR configuration
        frrconfig = self.getFRRconfig(zebra_route_map)
        self.assertNotIn(zebra_route_map, frrconfig)

if __name__ == '__main__':
    unittest.main(verbosity=2)
