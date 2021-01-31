#!/usr/bin/env python3
#
# Copyright (C) 2020-2021 VyOS maintainers and contributors
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

from netifaces import interfaces

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Interface
from vyos.ifconfig import Section
from vyos.template import is_ipv6
from vyos.util import cmd
from vyos.util import read_file
from vyos.validate import is_intf_addr_assigned

base_path = ['vrf']
vrfs = ['red', 'green', 'blue', 'foo-bar', 'baz_foo']

def get_vrf_ipv4_routes(vrf):
    return json.loads(cmd(f'ip -4 -j route show vrf {vrf}'))

def get_vrf_ipv6_routes(vrf):
    return json.loads(cmd(f'ip -6 -j route show vrf {vrf}'))

class VRFTest(unittest.TestCase):
    _interfaces = []

    @classmethod
    def setUpClass(cls):
        # we need to filter out VLAN interfaces identified by a dot (.)
        # in their name - just in case!
        if 'TEST_ETH' in os.environ:
            tmp = os.environ['TEST_ETH'].split()
            cls._interfaces = tmp
        else:
            for tmp in Section.interfaces('ethernet'):
                if not '.' in tmp:
                    cls._interfaces.append(tmp)

    def setUp(self):
        self.session = ConfigSession(os.getpid())

    def tearDown(self):
        # delete all VRFs
        self.session.delete(base_path)
        self.session.commit()
        for vrf in vrfs:
            self.assertNotIn(vrf, interfaces())

    def test_vrf_table_id(self):
        table = '1000'
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            description = f'VyOS-VRF-{vrf}'
            self.session.set(base + ['description', description])

            # check validate() - a table ID is mandatory
            with self.assertRaises(ConfigSessionError):
                self.session.commit()

            self.session.set(base + ['table', table])
            if vrf == 'green':
                self.session.set(base + ['disable'])

            table = str(int(table) + 1)

        # commit changes
        self.session.commit()

        # Verify VRF configuration
        table = '1000'
        iproute2_config = read_file('/etc/iproute2/rt_tables.d/vyos-vrf.conf')
        for vrf in vrfs:
            description = f'VyOS-VRF-{vrf}'
            self.assertTrue(vrf in interfaces())
            vrf_if = Interface(vrf)
            # validate proper interface description
            self.assertEqual(vrf_if.get_alias(), description)
            # validate admin up/down state of VRF
            state = 'up'
            if vrf == 'green':
                state = 'down'
            self.assertEqual(vrf_if.get_admin_state(), state)

            # Test the iproute2 lookup file, syntax is as follows:
            #
            # # id       vrf name         comment
            # 1000       red              # VyOS-VRF-red
            # 1001       green            # VyOS-VRF-green
            #  ...
            regex = f'{table}\s+{vrf}\s+#\s+{description}'
            self.assertTrue(re.findall(regex, iproute2_config))
            table = str(int(table) + 1)

    def test_vrf_loopback_ips(self):
        table = '2000'
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.session.set(base + ['table', str(table)])
            table = str(int(table) + 1)

        # commit changes
        self.session.commit()

        # Verify VRF configuration
        for vrf in vrfs:
            self.assertTrue(vrf in interfaces())
            self.assertTrue(is_intf_addr_assigned(vrf, '127.0.0.1'))
            self.assertTrue(is_intf_addr_assigned(vrf, '::1'))

    def test_vrf_table_id_is_unalterable(self):
        # Linux Kernel prohibits the change of a VRF table  on the fly.
        # VRF must be deleted and recreated!
        table = '1000'
        vrf = vrfs[0]
        base = base_path + ['name', vrf]
        self.session.set(base + ['table', table])

        # commit changes
        self.session.commit()

        # Check if VRF has been created
        self.assertTrue(vrf in interfaces())

        table = str(int(table) + 1)
        self.session.set(base + ['table', table])
        # check validate() - table ID can not be altered!
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

    def test_vrf_assign_interface(self):
        vrf = vrfs[0]
        table = '5000'
        self.session.set(['vrf', 'name', vrf, 'table', table])

        for interface in self._interfaces:
            section = Section.section(interface)
            self.session.set(['interfaces', section, interface, 'vrf', vrf])

        # commit changes
        self.session.commit()

        # Verify & cleanup
        for interface in self._interfaces:
            # os.readlink resolves to: '../../../../../virtual/net/foovrf'
            tmp = os.readlink(f'/sys/class/net/{interface}/master').split('/')[-1]
            self.assertEqual(tmp, vrf)
            # cleanup
            section = Section.section(interface)
            self.session.delete(['interfaces', section, interface, 'vrf'])

    def test_vrf_static_routes(self):
        routes = {
            '10.0.0.0/8' : {
                'next_hop' : '192.0.2.2',
                'distance' : '200',
                'next_hop_vrf' : 'default',
                },
            '172.16.0.0/12' : {
                'next_hop' : '192.0.2.3',
                'next_hop_vrf' : 'default',
                },
            '192.168.0.0/16' : {
                'next_hop' : '192.0.2.3',
                },
            '2001:db8:1000::/48' : {
                'next_hop' : '2001:db8::2',
                },
        }

        table = '2000'
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.session.set(base + ['table', str(table)])

            # required interface for leaking to default table
            self.session.set(['interfaces', 'ethernet', 'eth0', 'address', '192.0.2.1/24'])

            # we also need an interface in "UP" state to install routes
            self.session.set(['interfaces', 'dummy', f'dum{table}', 'vrf', vrf])
            self.session.set(['interfaces', 'dummy', f'dum{table}', 'address', '192.0.2.1/24'])
            self.session.set(['interfaces', 'dummy', f'dum{table}', 'address', '2001:db8::1/64'])
            table = str(int(table) + 1)

            proto_base = ['protocols', 'vrf', vrf, 'static']
            for route, route_config in routes.items():
                route_type = 'route'
                if is_ipv6(route):
                    route_type = 'route6'
                self.session.set(proto_base + [route_type, route, 'next-hop', route_config['next_hop']])
                if 'distance' in route_config:
                    self.session.set(proto_base + [route_type, route, 'next-hop', route_config['next_hop'], 'distance', route_config['distance']])
                if 'next_hop_vrf' in route_config:
                    self.session.set(proto_base + [route_type, route, 'next-hop', route_config['next_hop'], 'next-hop-vrf', route_config['next_hop_vrf']])

        # commit changes
        self.session.commit()

        # Verify routes
        table = '2000'
        for vrf in vrfs:
            for route, route_config in routes.items():
                if is_ipv6(route):
                    tmp = get_vrf_ipv6_routes(vrf)
                else:
                    tmp = get_vrf_ipv4_routes(vrf)

                found = False
                for result in tmp:
                    if 'dst' in result and result['dst'] == route:
                        if 'gateway' in result and result['gateway'] == route_config['next_hop']:
                            found = True

                self.assertTrue(found)

            # Cleanup
            self.session.delete(['protocols', 'vrf', vrf])
            self.session.delete(['interfaces', 'dummy', f'dum{table}'])
            self.session.delete(['interfaces', 'ethernet', 'eth0', 'address', '192.0.2.1/24'])

            table = str(int(table) + 1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
