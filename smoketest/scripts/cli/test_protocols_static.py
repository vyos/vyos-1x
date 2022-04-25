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

from vyos.configsession import ConfigSessionError
from vyos.template import is_ipv6
from vyos.util import get_interface_config

base_path = ['protocols', 'static']
vrf_path =  ['protocols', 'vrf']

routes = {
    '10.0.0.0/8' : {
        'next_hop' : {
            '192.0.2.100' : { 'distance' : '100' },
            '192.0.2.110' : { 'distance' : '110', 'interface' : 'eth0' },
            '192.0.2.120' : { 'distance' : '120', 'disable' : '' },
        },
        'interface' : {
            'eth0'  : { 'distance' : '130' },
            'eth1'  : { 'distance' : '140' },
        },
        'blackhole' : { 'distance' : '250', 'tag' : '500' },
    },
    '172.16.0.0/12' : {
        'interface' : {
            'eth0'  : { 'distance' : '50', 'vrf' : 'black' },
            'eth1'  : { 'distance' : '60', 'vrf' : 'black' },
        },
        'blackhole' : { 'distance' : '90' },
    },
    '192.0.2.0/24' : {
        'interface' : {
            'eth0'  : { 'distance' : '50', 'vrf' : 'black' },
            'eth1'  : { 'disable' : '' },
        },
        'blackhole' : { 'distance' : '90' },
    },
    '100.64.0.0/16' : {
        'blackhole' : { },
    },
    '100.65.0.0/16' : {
        'reject'    : { 'distance' : '10', 'tag' : '200' },
    },
    '100.66.0.0/16' : {
        'blackhole' : { },
        'reject'    : { 'distance' : '10', 'tag' : '200' },
    },
    '2001:db8:100::/40' : {
        'next_hop' : {
            '2001:db8::1' : { 'distance' : '10' },
            '2001:db8::2' : { 'distance' : '20', 'interface' : 'eth0' },
            '2001:db8::3' : { 'distance' : '30', 'disable' : '' },
        },
        'interface' : {
            'eth0'  : { 'distance' : '40', 'vrf' : 'black' },
            'eth1'  : { 'distance' : '50', 'disable' : '' },
        },
        'blackhole' : { 'distance' : '250', 'tag' : '500' },
    },
    '2001:db8:200::/40' : {
        'interface' : {
            'eth0'  : { 'distance' : '40' },
            'eth1'  : { 'distance' : '50', 'disable' : '' },
        },
        'blackhole' : { 'distance' : '250', 'tag' : '500' },
    },
    '2001:db8:300::/40' : {
        'reject'    : { 'distance' : '250', 'tag' : '500' },
    },
    '2001:db8::/32' : {
        'blackhole' : { 'distance' : '200', 'tag' : '600' },
    },
}

tables = ['80', '81', '82']

class TestProtocolsStatic(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProtocolsStatic, cls).setUpClass()
        cls.cli_set(cls, ['vrf', 'name', 'black', 'table', '43210'])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['vrf'])
        super(TestProtocolsStatic, cls).tearDownClass()

    def tearDown(self):
        for route, route_config in routes.items():
            route_type = 'route'
            if is_ipv6(route):
                route_type = 'route6'
            self.cli_delete(base_path + [route_type, route])

        for table in tables:
            self.cli_delete(base_path + ['table', table])

        tmp = self.getFRRconfig('', end='')
        self.cli_commit()

    def test_01_static(self):
        for route, route_config in routes.items():
            route_type = 'route'
            if is_ipv6(route):
                route_type = 'route6'
            base = base_path + [route_type, route]
            if 'next_hop' in route_config:
                for next_hop, next_hop_config in route_config['next_hop'].items():
                    self.cli_set(base + ['next-hop', next_hop])
                    if 'disable' in next_hop_config:
                        self.cli_set(base + ['next-hop', next_hop, 'disable'])
                    if 'distance' in next_hop_config:
                        self.cli_set(base + ['next-hop', next_hop, 'distance', next_hop_config['distance']])
                    if 'interface' in next_hop_config:
                        self.cli_set(base + ['next-hop', next_hop, 'interface', next_hop_config['interface']])
                    if 'vrf' in next_hop_config:
                        self.cli_set(base + ['next-hop', next_hop, 'vrf', next_hop_config['vrf']])


            if 'interface' in route_config:
                for interface, interface_config in route_config['interface'].items():
                    self.cli_set(base + ['interface', interface])
                    if 'disable' in interface_config:
                        self.cli_set(base + ['interface', interface, 'disable'])
                    if 'distance' in interface_config:
                        self.cli_set(base + ['interface', interface, 'distance', interface_config['distance']])
                    if 'vrf' in interface_config:
                        self.cli_set(base + ['interface', interface, 'vrf', interface_config['vrf']])

            if 'blackhole' in route_config:
                self.cli_set(base + ['blackhole'])
                if 'distance' in route_config['blackhole']:
                    self.cli_set(base + ['blackhole', 'distance', route_config['blackhole']['distance']])
                if 'tag' in route_config['blackhole']:
                    self.cli_set(base + ['blackhole', 'tag', route_config['blackhole']['tag']])

            if 'reject' in route_config:
                self.cli_set(base + ['reject'])
                if 'distance' in route_config['reject']:
                    self.cli_set(base + ['reject', 'distance', route_config['reject']['distance']])
                if 'tag' in route_config['reject']:
                    self.cli_set(base + ['reject', 'tag', route_config['reject']['tag']])

            if {'blackhole', 'reject'} <= set(route_config):
                # Can not use blackhole and reject at the same time
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
                self.cli_delete(base + ['blackhole'])
                self.cli_delete(base + ['reject'])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = self.getFRRconfig('ip route', end='')

        # Verify routes
        for route, route_config in routes.items():
            ip_ipv6 = 'ip'
            if is_ipv6(route):
                ip_ipv6 = 'ipv6'

            if 'next_hop' in route_config:
                for next_hop, next_hop_config in route_config['next_hop'].items():
                    tmp = f'{ip_ipv6} route {route} {next_hop}'
                    if 'interface' in next_hop_config:
                        tmp += ' ' + next_hop_config['interface']
                    if 'distance' in next_hop_config:
                        tmp += ' ' + next_hop_config['distance']
                    if 'vrf' in next_hop_config:
                        tmp += ' nexthop-vrf ' + next_hop_config['vrf']

                    if 'disable' in next_hop_config:
                        self.assertNotIn(tmp, frrconfig)
                    else:
                        self.assertIn(tmp, frrconfig)

            if 'interface' in route_config:
                for interface, interface_config in route_config['interface'].items():
                    tmp = f'{ip_ipv6} route {route} {interface}'
                    if 'interface' in interface_config:
                        tmp += ' ' + interface_config['interface']
                    if 'distance' in interface_config:
                        tmp += ' ' + interface_config['distance']
                    if 'vrf' in interface_config:
                        tmp += ' nexthop-vrf ' + interface_config['vrf']

                    if 'disable' in interface_config:
                        self.assertNotIn(tmp, frrconfig)
                    else:
                        self.assertIn(tmp, frrconfig)

            if {'blackhole', 'reject'} <= set(route_config):
                # Can not use blackhole and reject at the same time
                # Config error validated above - skip this route
                continue

            if 'blackhole' in route_config:
                tmp = f'{ip_ipv6} route {route} blackhole'
                if 'tag' in route_config['blackhole']:
                    tmp += ' tag ' + route_config['blackhole']['tag']
                if 'distance' in route_config['blackhole']:
                    tmp += ' ' + route_config['blackhole']['distance']

                self.assertIn(tmp, frrconfig)

            if 'reject' in route_config:
                tmp = f'{ip_ipv6} route {route} reject'
                if 'tag' in route_config['reject']:
                    tmp += ' tag ' + route_config['reject']['tag']
                if 'distance' in route_config['reject']:
                    tmp += ' ' + route_config['reject']['distance']

                self.assertIn(tmp, frrconfig)

    def test_02_static_table(self):
        for table in tables:
            for route, route_config in routes.items():
                route_type = 'route'
                if is_ipv6(route):
                    route_type = 'route6'
                base = base_path + ['table', table, route_type, route]

                if 'next_hop' in route_config:
                    for next_hop, next_hop_config in route_config['next_hop'].items():
                        self.cli_set(base + ['next-hop', next_hop])
                        if 'disable' in next_hop_config:
                            self.cli_set(base + ['next-hop', next_hop, 'disable'])
                        if 'distance' in next_hop_config:
                            self.cli_set(base + ['next-hop', next_hop, 'distance', next_hop_config['distance']])
                        if 'interface' in next_hop_config:
                            self.cli_set(base + ['next-hop', next_hop, 'interface', next_hop_config['interface']])
                        if 'vrf' in next_hop_config:
                            self.cli_set(base + ['next-hop', next_hop, 'vrf', next_hop_config['vrf']])


                if 'interface' in route_config:
                    for interface, interface_config in route_config['interface'].items():
                        self.cli_set(base + ['interface', interface])
                        if 'disable' in interface_config:
                            self.cli_set(base + ['interface', interface, 'disable'])
                        if 'distance' in interface_config:
                            self.cli_set(base + ['interface', interface, 'distance', interface_config['distance']])
                        if 'vrf' in interface_config:
                            self.cli_set(base + ['interface', interface, 'vrf', interface_config['vrf']])

                if 'blackhole' in route_config:
                    self.cli_set(base + ['blackhole'])
                    if 'distance' in route_config['blackhole']:
                        self.cli_set(base + ['blackhole', 'distance', route_config['blackhole']['distance']])
                    if 'tag' in route_config['blackhole']:
                        self.cli_set(base + ['blackhole', 'tag', route_config['blackhole']['tag']])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = self.getFRRconfig('ip route', end='')

        for table in tables:
            # Verify routes
            for route, route_config in routes.items():
                ip_ipv6 = 'ip'
                if is_ipv6(route):
                    ip_ipv6 = 'ipv6'

                if 'next_hop' in route_config:
                    for next_hop, next_hop_config in route_config['next_hop'].items():
                        tmp = f'{ip_ipv6} route {route} {next_hop}'
                        if 'interface' in next_hop_config:
                            tmp += ' ' + next_hop_config['interface']
                        if 'distance' in next_hop_config:
                            tmp += ' ' + next_hop_config['distance']
                        if 'vrf' in next_hop_config:
                            tmp += ' nexthop-vrf ' + next_hop_config['vrf']

                        tmp += ' table ' + table
                        if 'disable' in next_hop_config:
                            self.assertNotIn(tmp, frrconfig)
                        else:
                            self.assertIn(tmp, frrconfig)

                if 'interface' in route_config:
                    for interface, interface_config in route_config['interface'].items():
                        tmp = f'{ip_ipv6} route {route} {interface}'
                        if 'interface' in interface_config:
                            tmp += ' ' + interface_config['interface']
                        if 'distance' in interface_config:
                            tmp += ' ' + interface_config['distance']
                        if 'vrf' in interface_config:
                            tmp += ' nexthop-vrf ' + interface_config['vrf']

                        tmp += ' table ' + table
                        if 'disable' in interface_config:
                            self.assertNotIn(tmp, frrconfig)
                        else:
                            self.assertIn(tmp, frrconfig)

                if 'blackhole' in route_config:
                    tmp = f'{ip_ipv6} route {route} blackhole'
                    if 'tag' in route_config['blackhole']:
                        tmp += ' tag ' + route_config['blackhole']['tag']
                    if 'distance' in route_config['blackhole']:
                        tmp += ' ' + route_config['blackhole']['distance']

                    tmp += ' table ' + table
                    self.assertIn(tmp, frrconfig)


    def test_03_static_vrf(self):
        # Create VRF instances and apply the static routes from above to FRR.
        # Re-read the configured routes and match them if they are programmed
        # properly. This also includes VRF leaking
        vrfs = {
            'red'   : { 'table' : '1000' },
            'green' : { 'table' : '2000' },
            'blue'  : { 'table' : '3000' },
        }

        for vrf, vrf_config in vrfs.items():
            vrf_base_path = ['vrf', 'name', vrf]
            self.cli_set(vrf_base_path + ['table', vrf_config['table']])

            for route, route_config in routes.items():
                route_type = 'route'
                if is_ipv6(route):
                    route_type = 'route6'
                route_base_path = vrf_base_path + ['protocols', 'static', route_type, route]

                if 'next_hop' in route_config:
                    for next_hop, next_hop_config in route_config['next_hop'].items():
                        self.cli_set(route_base_path + ['next-hop', next_hop])
                        if 'disable' in next_hop_config:
                            self.cli_set(route_base_path + ['next-hop', next_hop, 'disable'])
                        if 'distance' in next_hop_config:
                            self.cli_set(route_base_path + ['next-hop', next_hop, 'distance', next_hop_config['distance']])
                        if 'interface' in next_hop_config:
                            self.cli_set(route_base_path + ['next-hop', next_hop, 'interface', next_hop_config['interface']])
                        if 'vrf' in next_hop_config:
                            self.cli_set(route_base_path + ['next-hop', next_hop, 'vrf', next_hop_config['vrf']])


                if 'interface' in route_config:
                    for interface, interface_config in route_config['interface'].items():
                        self.cli_set(route_base_path + ['interface', interface])
                        if 'disable' in interface_config:
                            self.cli_set(route_base_path + ['interface', interface, 'disable'])
                        if 'distance' in interface_config:
                            self.cli_set(route_base_path + ['interface', interface, 'distance', interface_config['distance']])
                        if 'vrf' in interface_config:
                            self.cli_set(route_base_path + ['interface', interface, 'vrf', interface_config['vrf']])

                if 'blackhole' in route_config:
                    self.cli_set(route_base_path + ['blackhole'])
                    if 'distance' in route_config['blackhole']:
                        self.cli_set(route_base_path + ['blackhole', 'distance', route_config['blackhole']['distance']])
                    if 'tag' in route_config['blackhole']:
                        self.cli_set(route_base_path + ['blackhole', 'tag', route_config['blackhole']['tag']])

        # commit changes
        self.cli_commit()

        for vrf, vrf_config in vrfs.items():
            tmp = get_interface_config(vrf)

            # Compare VRF table ID
            self.assertEqual(tmp['linkinfo']['info_data']['table'], int(vrf_config['table']))
            self.assertEqual(tmp['linkinfo']['info_kind'],          'vrf')

            # Verify FRR bgpd configuration
            frrconfig = self.getFRRconfig(f'vrf {vrf}')
            self.assertIn(f'vrf {vrf}', frrconfig)

            # Verify routes
            for route, route_config in routes.items():
                ip_ipv6 = 'ip'
                if is_ipv6(route):
                    ip_ipv6 = 'ipv6'

                if 'next_hop' in route_config:
                    for next_hop, next_hop_config in route_config['next_hop'].items():
                        tmp = f'{ip_ipv6} route {route} {next_hop}'
                        if 'interface' in next_hop_config:
                            tmp += ' ' + next_hop_config['interface']
                        if 'distance' in next_hop_config:
                            tmp += ' ' + next_hop_config['distance']
                        if 'vrf' in next_hop_config:
                            tmp += ' nexthop-vrf ' + next_hop_config['vrf']

                        if 'disable' in next_hop_config:
                            self.assertNotIn(tmp, frrconfig)
                        else:
                            self.assertIn(tmp, frrconfig)

                if 'interface' in route_config:
                    for interface, interface_config in route_config['interface'].items():
                        tmp = f'{ip_ipv6} route {route} {interface}'
                        if 'interface' in interface_config:
                            tmp += ' ' + interface_config['interface']
                        if 'distance' in interface_config:
                            tmp += ' ' + interface_config['distance']
                        if 'vrf' in interface_config:
                            tmp += ' nexthop-vrf ' + interface_config['vrf']

                        if 'disable' in interface_config:
                            self.assertNotIn(tmp, frrconfig)
                        else:
                            self.assertIn(tmp, frrconfig)

                if 'blackhole' in route_config:
                    tmp = f'{ip_ipv6} route {route} blackhole'
                    if 'tag' in route_config['blackhole']:
                        tmp += ' tag ' + route_config['blackhole']['tag']
                    if 'distance' in route_config['blackhole']:
                        tmp += ' ' + route_config['blackhole']['distance']

                    self.assertIn(tmp, frrconfig)

    def test_04_static_zebra_route_map(self):
        # Implemented because of T3328
        route_map = 'foo-static-in'
        self.cli_set(['policy', 'route-map', route_map, 'rule', '10', 'action', 'permit'])

        self.cli_set(base_path + ['route-map', route_map])
        # commit changes
        self.cli_commit()

        # Verify FRR configuration
        zebra_route_map = f'ip protocol static route-map {route_map}'
        frrconfig = self.getFRRconfig(zebra_route_map)
        self.assertIn(zebra_route_map, frrconfig)

        # Remove the route-map again
        self.cli_delete(base_path + ['route-map'])
        # commit changes
        self.cli_commit()

        # Verify FRR configuration
        frrconfig = self.getFRRconfig(zebra_route_map)
        self.assertNotIn(zebra_route_map, frrconfig)

        self.cli_delete(['policy', 'route-map', route_map])

if __name__ == '__main__':
    unittest.main(verbosity=2)
