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

import os
import unittest

from time import sleep
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.template import is_ipv6
from vyos.template import get_dhcp_router
from vyos.utils.network import get_interface_config
from vyos.utils.network import get_vrf_tableid
from vyos.utils.process import process_named_running
from vyos.xml_ref import default_value

base_path = ['protocols', 'static']
vrf_path =  ['protocols', 'vrf']

routes = {
    '10.0.0.0/8' : {
        'next_hop' : {
            '192.0.2.100' : { 'distance' : '100' },
            '192.0.2.110' : { 'distance' : '110', 'interface' : 'eth0' },
            '192.0.2.120' : { 'distance' : '120', 'disable' : '' },
            '192.0.2.130' : { 'bfd' : '' },
            '192.0.2.131' : { 'bfd' : '',
                              'bfd_profile' : 'vyos1' },
            '192.0.2.140' : { 'bfd' : '',
                              'bfd_source' : '192.0.2.10',
                              'bfd_profile' : 'vyos2' },
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
        'blackhole' : {},
    },
    '100.65.0.0/16' : {
        'reject'    : { 'distance' : '10', 'tag' : '200' },
    },
    '100.66.0.0/16' : {
        'blackhole' : {},
        'reject'    : { 'distance' : '10', 'tag' : '200' },
    },
    '2001:db8:100::/40' : {
        'next_hop' : {
            '2001:db8::1' : { 'distance' : '10' },
            '2001:db8::2' : { 'distance' : '20', 'interface' : 'eth0' },
            '2001:db8::3' : { 'distance' : '30', 'disable' : '' },
            '2001:db8::4' : { 'bfd' : '' },
            '2001:db8::5' : { 'bfd_source' : '2001:db8::ffff' },
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
    '2001:db8:400::/40' : {
        'next_hop' : {
            '2001:db8::400' : { 'segments' : '2001:db8:aaaa::400/2002::400/2003::400/2004::400' },
        },
    },
    '2001:db8:500::/40' : {
        'next_hop' : {
            '2001:db8::500' : { 'segments' : '2001:db8:aaaa::500/2002::500/2003::500/2004::500' },
        },
    },
    '2001:db8:600::/40' : {
        'interface' : {
            'eth0'  : { 'segments' : '2001:db8:aaaa::600/2002::600' },
        },
    },
    '2001:db8:700::/40' : {
        'interface' : {
            'eth1'  : { 'segments' : '2001:db8:aaaa::700' },
        },
    },
    '2001:db8::/32' : {
        'blackhole' : { 'distance' : '200', 'tag' : '600' }
    },
}

multicast_routes = {
    '224.0.0.0/24' : {
        'next_hop' : {
            '224.203.0.1' : { },
            '224.203.0.2' : { 'distance' : '110'},
        },
    },
    '224.1.0.0/24' : {
        'next_hop' : {
            '224.205.0.1' : { 'disable' : {} },
            '224.205.0.2' : { 'distance' : '110'},
        },
    },
    '224.2.0.0/24' : {
        'next_hop' : {
            '1.2.3.0' : { },
            '1.2.3.1' : { 'distance' : '110'},
        },
    },
    '224.10.0.0/24' : {
        'interface' : {
            'eth1' : { 'disable' : {} },
            'eth2' : { 'distance' : '110'},
        },
    },
    '224.11.0.0/24' : {
        'interface' : {
            'eth0' : { },
            'eth1' : { 'distance' : '10'},
        },
    },
    '224.12.0.0/24' : {
        'interface' : {
            'eth0' : { },
            'eth1' : { 'distance' : '200'},
        },
    },
}

tables = ['80', '81', '82']

class TestProtocolsStatic(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProtocolsStatic, cls).setUpClass()
        cls.cli_delete(cls, base_path)
        cls.cli_delete(cls, ['vrf'])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, base_path)
        cls.cli_delete(cls, ['vrf'])
        super(TestProtocolsStatic, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_delete(['vrf'])
        self.cli_commit()

        v4route = self.getFRRconfig('ip route')
        self.assertFalse(v4route)
        v6route = self.getFRRconfig('ipv6 route')
        self.assertFalse(v6route)

        # always forward to base class
        super().tearDown()

    def test_01_static(self):
        self.cli_set(['vrf', 'name', 'black', 'table', '43210'])
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
                    if 'bfd' in next_hop_config:
                        self.cli_set(base + ['next-hop', next_hop, 'bfd'])
                        if 'bfd_profile' in next_hop_config:
                            self.cli_set(base + ['next-hop', next_hop, 'bfd', 'profile', next_hop_config['bfd_profile']])
                        if 'bfd_source' in next_hop_config:
                            self.cli_set(base + ['next-hop', next_hop, 'bfd', 'multi-hop', 'source-address', next_hop_config['bfd_source']])
                    if 'segments' in next_hop_config:
                        self.cli_set(base + ['next-hop', next_hop, 'segments', next_hop_config['segments']])

            if 'interface' in route_config:
                for interface, interface_config in route_config['interface'].items():
                    self.cli_set(base + ['interface', interface])
                    if 'disable' in interface_config:
                        self.cli_set(base + ['interface', interface, 'disable'])
                    if 'distance' in interface_config:
                        self.cli_set(base + ['interface', interface, 'distance', interface_config['distance']])
                    if 'vrf' in interface_config:
                        self.cli_set(base + ['interface', interface, 'vrf', interface_config['vrf']])
                    if 'segments' in interface_config:
                        self.cli_set(base + ['interface', interface, 'segments', interface_config['segments']])

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
        frrconfig = self.getFRRconfig('ip route')

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
                    if 'bfd' in next_hop_config:
                        tmp += ' bfd'
                        if 'bfd_source' in next_hop_config:
                            tmp += ' multi-hop source ' + next_hop_config['bfd_source']
                        if 'bfd_profile' in next_hop_config:
                            tmp += ' profile ' + next_hop_config['bfd_profile']
                    if 'segments' in next_hop_config:
                        tmp += ' segments ' + next_hop_config['segments']

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
                    if 'segments' in interface_config:
                        tmp += ' segments ' + interface_config['segments']

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
        self.cli_set(['vrf', 'name', 'black', 'table', '43210'])
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
        frrconfig = self.getFRRconfig('ip route')

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
        self.cli_set(['vrf', 'name', 'black', 'table', '43210'])
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
                        if 'segments' in next_hop_config:
                            self.cli_set(route_base_path + ['next-hop', next_hop, 'segments', next_hop_config['segments']])

                if 'interface' in route_config:
                    for interface, interface_config in route_config['interface'].items():
                        self.cli_set(route_base_path + ['interface', interface])
                        if 'disable' in interface_config:
                            self.cli_set(route_base_path + ['interface', interface, 'disable'])
                        if 'distance' in interface_config:
                            self.cli_set(route_base_path + ['interface', interface, 'distance', interface_config['distance']])
                        if 'vrf' in interface_config:
                            self.cli_set(route_base_path + ['interface', interface, 'vrf', interface_config['vrf']])
                        if 'segments' in interface_config:
                            self.cli_set(route_base_path + ['interface', interface, 'segments', interface_config['segments']])

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
            self.assertEqual(get_vrf_tableid(vrf), int(vrf_config['table']))
            self.assertEqual(tmp['linkinfo']['info_kind'],          'vrf')

            # Verify FRR bgpd configuration
            frrconfig = self.getFRRconfig(f'vrf {vrf}', stop_section='^exit-vrf')
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
                        if 'segments' in next_hop_config:
                            tmp += ' segments ' + next_hop_config['segments']

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
                        if 'segments' in interface_config:
                            tmp += ' segments ' + interface_config['segments']

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

    def test_04_static_multicast(self):
        for route, route_config in multicast_routes.items():
            if 'next_hop' in route_config:
                base = base_path + ['mroute', route]
                for next_hop, next_hop_config in route_config['next_hop'].items():
                    self.cli_set(base + ['next-hop', next_hop])
                    if 'distance' in next_hop_config:
                        self.cli_set(base + ['next-hop', next_hop, 'distance', next_hop_config['distance']])
                    if 'disable' in next_hop_config:
                        self.cli_set(base + ['next-hop', next_hop, 'disable'])

            if 'interface' in route_config:
                base = base_path + ['mroute', route]
                for next_hop, next_hop_config in route_config['interface'].items():
                    self.cli_set(base + ['interface', next_hop])
                    if 'distance' in next_hop_config:
                        self.cli_set(base + ['interface', next_hop, 'distance', next_hop_config['distance']])

        self.cli_commit()

        # Verify FRR configuration
        frrconfig = self.getFRRconfig('ip mroute')
        for route, route_config in multicast_routes.items():
            if 'next_hop' in route_config:
                for next_hop, next_hop_config in route_config['next_hop'].items():
                    tmp = f'ip mroute {route} {next_hop}'
                    if 'distance' in next_hop_config:
                        tmp += ' ' + next_hop_config['distance']
                    if 'disable' in next_hop_config:
                        self.assertNotIn(tmp, frrconfig)
                    else:
                        self.assertIn(tmp, frrconfig)

            if 'next_hop_interface' in route_config:
                for next_hop, next_hop_config in route_config['next_hop_interface'].items():
                    tmp = f'ip mroute {route} {next_hop}'
                    if 'distance' in next_hop_config:
                        tmp += ' ' + next_hop_config['distance']
                    if 'disable' in next_hop_config:
                        self.assertNotIn(tmp, frrconfig)
                    else:
                        self.assertIn(tmp, frrconfig)

    def test_05_dhcp_default_route(self):
        # When running via vyos-build under the QEMU environment a local DHCP
        # server is available. This test verifies that the default route is set.
        # When not running under the VyOS QEMU environment, this test is skipped.
        if not os.path.exists('/tmp/vyos.smoketests.hint'):
            self.skipTest('Not running under VyOS CI/CD QEMU environment!')

        interface = 'eth0'
        interface_path = ['interfaces', 'ethernet', interface]
        default_distance = default_value(interface_path + ['dhcp-options', 'default-route-distance'])
        self.cli_set(interface_path + ['address', 'dhcp'])
        self.cli_commit()

        # Wait for dhclient to receive IP address and default gateway
        sleep(5)

        router = get_dhcp_router(interface)
        frrconfig = self.getFRRconfig()
        self.assertIn(rf'ip route 0.0.0.0/0 {router} {interface} tag 210 {default_distance}', frrconfig)

        # T6991: Default route is missing when there is no "protocols static"
        # CLI node entry
        self.cli_delete(base_path)
        # We can trigger a FRR reconfiguration and config re-rendering when
        # we simply disable IPv6 forwarding
        self.cli_set(['system', 'ipv6', 'disable-forwarding'])
        self.cli_commit()

        # Re-check FRR configuration that default route is still present
        frrconfig = self.getFRRconfig()
        self.assertIn(rf'ip route 0.0.0.0/0 {router} {interface} tag 210 {default_distance}', frrconfig)

        self.cli_delete(interface_path + ['address'])
        self.cli_commit()

        # Wait for dhclient to stop
        while process_named_running('dhclient', cmdline=interface, timeout=10):
            sleep(0.250)

    def test_06_dhcp_default_route_for_vrf(self):
        # When running via vyos-build under the QEMU environment a local DHCP
        # server is available. This test verifies that the default route is set.
        # When not running under the VyOS QEMU environment, this test is skipped.
        if not os.path.exists('/tmp/vyos.smoketests.hint'):
            self.skipTest('Not running under VyOS CI/CD QEMU environment!')

        interface = 'eth0'
        vrf = 'red'
        vrf_path = ['vrf', 'name', vrf]
        interface_path = ['interfaces', 'ethernet', interface]
        self.cli_set(vrf_path + ['table', '1000'])
        default_distance = default_value(interface_path + ['dhcp-options', 'default-route-distance'])
        self.cli_set(interface_path + ['address', 'dhcp'])
        self.cli_set(interface_path + ['vrf', vrf])
        self.cli_commit()

        # Wait for dhclient to receive IP address and default gateway
        sleep(5)

        router = get_dhcp_router(interface)
        frrconfig = self.getFRRconfig(f'vrf {vrf}', stop_section='^exit-vrf')
        self.assertIn(rf'ip route 0.0.0.0/0 {router} {interface} tag 210 {default_distance}', frrconfig)

        self.cli_delete(interface_path + ['address'])
        self.cli_delete(interface_path + ['vrf'])
        self.cli_commit()

        # Wait for dhclient to stop
        while process_named_running('dhclient', cmdline=interface, timeout=10):
            sleep(0.250)

    def test_07_dhcp_interface_static_routes(self):
        # Test static routes using dhcp-interface option
        # When running via vyos-build under the QEMU environment a local DHCP
        # server is available. This test verifies that static routes with
        # dhcp-interface are configured correctly.
        if not os.path.exists('/tmp/vyos.smoketests.hint'):
            self.skipTest('Not running under VyOS CI/CD QEMU environment!')

        dhcp_interface = 'eth0'
        interface_path = ['interfaces', 'ethernet', dhcp_interface]

        # Configure DHCP on the interface
        self.cli_set(interface_path + ['address', 'dhcp'])

        # Commit configuration
        self.cli_commit()

        # Wait for dhclient to receive IP address
        sleep(5)

        # Configure static routes with dhcp-interface
        dhcp_routes = {
            '10.10.0.0/16': {
                'dhcp_interface': [dhcp_interface],
            },
            '192.168.100.0/24': {
                'dhcp_interface': [dhcp_interface],
            },
        }

        # Configure the static routes
        for route, route_config in dhcp_routes.items():
            base = base_path + ['route', route]
            if 'dhcp_interface' in route_config:
                for dhcp_if in route_config['dhcp_interface']:
                    self.cli_set(base + ['dhcp-interface', dhcp_if])

        # Commit configuration
        self.cli_commit()

        # Verify that the DHCP hook interface list file is created
        dhcp_hook_iflist = '/tmp/static_dhcp_interfaces'
        self.assertTrue(
            os.path.exists(dhcp_hook_iflist),
            'DHCP hook interface list file should be created',
        )

        # Read the interface list file and verify it contains our interface
        with open(dhcp_hook_iflist, 'r') as f:
            interface_list = f.read().strip()
        self.assertIn(
            dhcp_interface,
            interface_list,
            f'Interface {dhcp_interface} should be in hook interface list',
        )

        # Get the DHCP router for verification
        router = get_dhcp_router(dhcp_interface)
        self.assertIsNotNone(router, 'DHCP router should be available')

        # Verify FRR configuration contains the static routes with DHCP router
        frrconfig = self.getFRRconfig('ip route')

        for route in dhcp_routes.keys():
            expected_route = f'ip route {route} {router} {dhcp_interface}'
            self.assertIn(
                expected_route,
                frrconfig,
                f'Static route {route} with dhcp-interface should be in FRR config',
            )

        # Test table-based routes with dhcp-interface
        table_id = '100'
        table_route = '10.20.0.0/16'
        table_base = base_path + ['table', table_id, 'route', table_route]
        self.cli_set(table_base + ['dhcp-interface', dhcp_interface])
        self.cli_commit()

        # Verify table route in FRR config
        frrconfig = self.getFRRconfig('ip route')
        expected_table_route = (
            f'ip route {table_route} {router} {dhcp_interface} table {table_id}'
        )
        self.assertIn(
            expected_table_route,
            frrconfig,
            f'Table static route {table_route} with dhcp-interface should be in FRR config',
        )

        # Clean up - remove DHCP configuration
        self.cli_delete(interface_path + ['address'])
        self.cli_commit()

        # Wait for dhclient to stop
        while process_named_running('dhclient', cmdline=dhcp_interface, timeout=10):
            sleep(0.250)

        # Verify that the hook interface list file is cleaned up when no dhcp-interface routes exist
        self.cli_delete(base_path)
        self.cli_commit()

        # The interface list file should be removed when no dhcp-interface routes are configured
        self.assertFalse(
            os.path.exists(dhcp_hook_iflist),
            'DHCP hook interface list file should be removed when no dhcp-interface routes exist',
        )

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
