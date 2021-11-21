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

import re
import os
import json
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from netifaces import interfaces

from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Interface
from vyos.ifconfig import Section
from vyos.template import is_ipv6
from vyos.util import cmd
from vyos.util import read_file
from vyos.validate import is_intf_addr_assigned

dummy_if = 'dum08765'
base_path = ['protocols', 'static']

routes = {
    '10.0.0.0/8' : {
        'next_hop' : '192.0.2.2',
        'distance' : '200',
    },
    '172.16.0.0/12' : {
        'next_hop' : '192.0.2.3',
    },
    '192.168.0.0/16' : {
        'next_hop' : '192.0.2.3',
    },
    '2001:db8:1000::/48' : {
        'next_hop' : '2001:db8::1000',
    },
    '2001:db8:2000::/48' : {
        'next_hop' : '2001:db8::2000',
    },
}

interface_routes = {
    '10.0.0.0/8' : {
        'next_hop' : dummy_if,
        'distance' : '200',
    },
    '172.16.0.0/12' : {
        'next_hop' : dummy_if,
    },
    '192.168.0.0/16' : {
        'next_hop' : dummy_if,
    },
    '2001:db8:1000::/48' : {
        'next_hop' : dummy_if,
    },
    '2001:db8:2000::/48' : {
        'next_hop' : dummy_if,
    },
}

class StaticRouteTest(VyOSUnitTestSHIM.TestCase):
    def setUp(self):
        # we need an alive next-hop interface
        self.cli_set(['interfaces', 'dummy', dummy_if, 'address', '192.0.2.1/24'])
        self.cli_set(['interfaces', 'dummy', dummy_if, 'address', '2001:db8::1/64'])

    def tearDown(self):
        self.cli_delete(['interfaces', 'dummy', dummy_if])
        self.cli_commit()

    def test_static_routes(self):
        for route, route_config in routes.items():
            route_type = 'route'
            if is_ipv6(route):
                route_type = 'route6'
            self.cli_set(base_path + [route_type, route, 'next-hop', route_config['next_hop']])
            if 'distance' in route_config:
                self.cli_set(base_path + [route_type, route, 'next-hop', route_config['next_hop'], 'distance', route_config['distance']])

        # commit changes
        self.cli_commit()

        # Verify routes
        for route, route_config in routes.items():
            ip_ver = '-4'
            if is_ipv6(route):
                ip_ver = '-6'
            tmp = json.loads(cmd(f'ip {ip_ver} -d -j route show {route}'))

            found = False
            for result in tmp:
                # unfortunately iproute2 does not return the distance
                if 'dst' in result and result['dst'] == route:
                    if 'gateway' in result and result['gateway'] == route_config['next_hop']:
                        found = True

            self.assertTrue(found)

            route_type = 'route'
            if is_ipv6(route):
                route_type = 'route6'
            self.cli_delete(base_path + [route_type, route])

    def test_interface_routes(self):
        for route, route_config in interface_routes.items():
            route_type = 'interface-route'
            if is_ipv6(route):
                route_type = 'interface-route6'
            self.cli_set(base_path + [route_type, route, 'next-hop-interface', route_config['next_hop']])
            if 'distance' in route_config:
                self.cli_set(base_path + [route_type, route, 'next-hop-interface', route_config['next_hop'], 'distance', route_config['distance']])

        # commit changes
        self.cli_commit()

        # Verify routes
        for route, route_config in interface_routes.items():
            ip_ver = '-4'
            if is_ipv6(route):
                ip_ver = '-6'
            tmp = json.loads(cmd(f'ip {ip_ver} -d -j route show {route}'))

            found = False
            for result in tmp:
                # unfortunately iproute2 does not return the distance
                if 'dst' in result and result['dst'] == route:
                    if 'dev' in result and result['dev'] == route_config['next_hop']:
                        found = True
                        break

            self.assertTrue(found)

            route_type = 'interface-route'
            if is_ipv6(route):
                route_type = 'interface-route6'
            self.cli_delete(base_path + [route_type, route])

if __name__ == '__main__':
    unittest.main(verbosity=2)
