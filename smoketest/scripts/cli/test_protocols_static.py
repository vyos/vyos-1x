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

import os
import unittest

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.template import is_ipv6
from vyos.util import cmd

base_path = ['protocols', 'static']
vrf_path =  ['protocols', 'vrf']

def getFRRCconfig(vrf=None):
    if vrf:
        return cmd(f'vtysh -c "show run" | sed -n "/^vrf {vrf}/,/^!/p"')
    else:
        return cmd(f'vtysh -c "show run" | sed -n "/^ip route/,/^!/p"')

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
    '100.64.0.0/10' : {
        'blackhole' : { },
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
    '2001:db8::/32' : {
        'blackhole' : { 'distance' : '200', 'tag' : '600' },
    },
}

vrfs = ['red', 'green', 'blue']
tables = ['80', '81', '82']

class StaticRouteTest(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())

    def tearDown(self):
        for route, route_config in routes.items():
            route_type = 'route'
            if is_ipv6(route):
                route_type = 'route6'
            self.session.delete(base_path + [route_type, route])

        for vrf in vrfs:
            self.session.delete(vrf_path + [vrf])

        for table in tables:
            self.session.delete(base_path + ['table', table])

        self.session.commit()
        del self.session

    def test_protocols_static(self):
        for route, route_config in routes.items():
            route_type = 'route'
            if is_ipv6(route):
                route_type = 'route6'
            base = base_path + [route_type, route]
            if 'next_hop' in route_config:
                for next_hop, next_hop_config in route_config['next_hop'].items():
                    self.session.set(base + ['next-hop', next_hop])
                    if 'disable' in next_hop_config:
                        self.session.set(base + ['next-hop', next_hop, 'disable'])
                    if 'distance' in next_hop_config:
                        self.session.set(base + ['next-hop', next_hop, 'distance', next_hop_config['distance']])
                    if 'interface' in next_hop_config:
                        self.session.set(base + ['next-hop', next_hop, 'interface', next_hop_config['interface']])
                    if 'vrf' in next_hop_config:
                        self.session.set(base + ['next-hop', next_hop, 'vrf', next_hop_config['vrf']])


            if 'interface' in route_config:
                for interface, interface_config in route_config['interface'].items():
                    self.session.set(base + ['interface', interface])
                    if 'disable' in interface_config:
                        self.session.set(base + ['interface', interface, 'disable'])
                    if 'distance' in interface_config:
                        self.session.set(base + ['interface', interface, 'distance', interface_config['distance']])
                    if 'vrf' in interface_config:
                        self.session.set(base + ['interface', interface, 'vrf', interface_config['vrf']])

            if 'blackhole' in route_config:
                self.session.set(base + ['blackhole'])
                if 'distance' in route_config['blackhole']:
                    self.session.set(base + ['blackhole', 'distance', route_config['blackhole']['distance']])
                if 'tag' in route_config['blackhole']:
                    self.session.set(base + ['blackhole', 'tag', route_config['blackhole']['tag']])

        # commit changes
        self.session.commit()

        # Verify FRR bgpd configuration
        frrconfig = getFRRCconfig()

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

    def test_protocols_static_table(self):
        for table in tables:
            for route, route_config in routes.items():
                route_type = 'route'
                if is_ipv6(route):
                    route_type = 'route6'
                base = base_path + ['table', table, route_type, route]

                if 'next_hop' in route_config:
                    for next_hop, next_hop_config in route_config['next_hop'].items():
                        self.session.set(base + ['next-hop', next_hop])
                        if 'disable' in next_hop_config:
                            self.session.set(base + ['next-hop', next_hop, 'disable'])
                        if 'distance' in next_hop_config:
                            self.session.set(base + ['next-hop', next_hop, 'distance', next_hop_config['distance']])
                        if 'interface' in next_hop_config:
                            self.session.set(base + ['next-hop', next_hop, 'interface', next_hop_config['interface']])

                        # This is currently not supported because of an FRR issue:
                        # https://github.com/FRRouting/frr/issues/8016
                        # if 'vrf' in next_hop_config:
                        #     self.session.set(base + ['next-hop', next_hop, 'vrf', next_hop_config['vrf']])


                if 'interface' in route_config:
                    for interface, interface_config in route_config['interface'].items():
                        self.session.set(base + ['interface', interface])
                        if 'disable' in interface_config:
                            self.session.set(base + ['interface', interface, 'disable'])
                        if 'distance' in interface_config:
                            self.session.set(base + ['interface', interface, 'distance', interface_config['distance']])

                        # This is currently not supported because of an FRR issue:
                        # https://github.com/FRRouting/frr/issues/8016
                        # if 'vrf' in interface_config:
                        #     self.session.set(base + ['interface', interface, 'vrf', interface_config['vrf']])

                if 'blackhole' in route_config:
                    self.session.set(base + ['blackhole'])
                    if 'distance' in route_config['blackhole']:
                        self.session.set(base + ['blackhole', 'distance', route_config['blackhole']['distance']])
                    if 'tag' in route_config['blackhole']:
                        self.session.set(base + ['blackhole', 'tag', route_config['blackhole']['tag']])

        # commit changes
        self.session.commit()

        # Verify FRR bgpd configuration
        frrconfig = getFRRCconfig()

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
                        # This is currently not supported because of an FRR issue:
                        # https://github.com/FRRouting/frr/issues/8016
                        # if 'vrf' in next_hop_config:
                        #     tmp += ' nexthop-vrf ' + next_hop_config['vrf']

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
                        # This is currently not supported because of an FRR issue:
                        # https://github.com/FRRouting/frr/issues/8016
                        # if 'vrf' in interface_config:
                        #     tmp += ' nexthop-vrf ' + interface_config['vrf']

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


    def test_protocols_vrf_static(self):
        for vrf in vrfs:
            for route, route_config in routes.items():
                route_type = 'route'
                if is_ipv6(route):
                    route_type = 'route6'
                base = vrf_path + [vrf, 'static', route_type, route]

                if 'next_hop' in route_config:
                    for next_hop, next_hop_config in route_config['next_hop'].items():
                        self.session.set(base + ['next-hop', next_hop])
                        if 'disable' in next_hop_config:
                            self.session.set(base + ['next-hop', next_hop, 'disable'])
                        if 'distance' in next_hop_config:
                            self.session.set(base + ['next-hop', next_hop, 'distance', next_hop_config['distance']])
                        if 'interface' in next_hop_config:
                            self.session.set(base + ['next-hop', next_hop, 'interface', next_hop_config['interface']])
                        if 'vrf' in next_hop_config:
                            self.session.set(base + ['next-hop', next_hop, 'vrf', next_hop_config['vrf']])


                if 'interface' in route_config:
                    for interface, interface_config in route_config['interface'].items():
                        self.session.set(base + ['interface', interface])
                        if 'disable' in interface_config:
                            self.session.set(base + ['interface', interface, 'disable'])
                        if 'distance' in interface_config:
                            self.session.set(base + ['interface', interface, 'distance', interface_config['distance']])
                        if 'vrf' in interface_config:
                            self.session.set(base + ['interface', interface, 'vrf', interface_config['vrf']])

                if 'blackhole' in route_config:
                    self.session.set(base + ['blackhole'])
                    if 'distance' in route_config['blackhole']:
                        self.session.set(base + ['blackhole', 'distance', route_config['blackhole']['distance']])
                    if 'tag' in route_config['blackhole']:
                        self.session.set(base + ['blackhole', 'tag', route_config['blackhole']['tag']])

        # commit changes
        self.session.commit()

        for vrf in vrfs:
            # Verify FRR bgpd configuration
            frrconfig = getFRRCconfig(vrf)
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
