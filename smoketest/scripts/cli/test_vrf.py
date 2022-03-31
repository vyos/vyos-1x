#!/usr/bin/env python3
#
# Copyright (C) 2020-2022 VyOS maintainers and contributors
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
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Interface
from vyos.ifconfig import Section
from vyos.template import is_ipv4
from vyos.util import cmd
from vyos.util import read_file
from vyos.util import get_interface_config
from vyos.validate import is_intf_addr_assigned

base_path = ['vrf']
vrfs = ['red', 'green', 'blue', 'foo-bar', 'baz_foo']

class VRFTest(VyOSUnitTestSHIM.TestCase):
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
        # call base-classes classmethod
        super(cls, cls).setUpClass()

    def tearDown(self):
        # delete all VRFs
        self.cli_delete(base_path)
        self.cli_commit()
        for vrf in vrfs:
            self.assertNotIn(vrf, interfaces())

    def test_vrf_vni_and_table_id(self):
        table = '1000'
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            description = f'VyOS-VRF-{vrf}'
            self.cli_set(base + ['description', description])

            # check validate() - a table ID is mandatory
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()

            self.cli_set(base + ['table', table])
            self.cli_set(base + ['vni', table])
            if vrf == 'green':
                self.cli_set(base + ['disable'])

            table = str(int(table) + 1)

        # commit changes
        self.cli_commit()

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

            frrconfig = self.getFRRconfig(f'vrf {vrf}')
            self.assertIn(f' vni {table}', frrconfig)

            tmp = get_interface_config(vrf)
            self.assertEqual(int(table), tmp['linkinfo']['info_data']['table'])

            # Increment table ID for the next run
            table = str(int(table) + 1)

    def test_vrf_loopbacks_ips(self):
        table = '2000'
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_set(base + ['table', str(table)])
            table = str(int(table) + 1)

        # commit changes
        self.cli_commit()

        # Verify VRF configuration
        loopbacks = ['127.0.0.1', '::1']
        for vrf in vrfs:
            # Ensure VRF was created
            self.assertIn(vrf, interfaces())
            # Test for proper loopback IP assignment
            for addr in loopbacks:
                self.assertTrue(is_intf_addr_assigned(vrf, addr))

    def test_vrf_loopbacks_no_ipv6(self):
        table = '2002'
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_set(base + ['table', str(table)])
            table = str(int(table) + 1)

        # Globally disable IPv6 - this will remove all IPv6 interface addresses
        self.cli_set(['system', 'ipv6', 'disable'])

        # commit changes
        self.cli_commit()

        # Verify VRF configuration
        table = '2002'
        loopbacks = ['127.0.0.1', '::1']
        for vrf in vrfs:
            # Ensure VRF was created
            self.assertIn(vrf, interfaces())

            # Verify VRF table ID
            tmp = get_interface_config(vrf)
            self.assertEqual(int(table), tmp['linkinfo']['info_data']['table'])

            # Test for proper loopback IP assignment
            for addr in loopbacks:
                if is_ipv4(addr):
                    self.assertTrue(is_intf_addr_assigned(vrf, addr))
                else:
                    self.assertFalse(is_intf_addr_assigned(vrf, addr))

            table = str(int(table) + 1)

        self.cli_delete(['system', 'ipv6'])

    def test_vrf_bind_all(self):
        table = '2000'
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_set(base + ['table', str(table)])
            table = str(int(table) + 1)

        self.cli_set(base_path +  ['bind-to-all'])

        # commit changes
        self.cli_commit()

        # Verify VRF configuration
        tmp = read_file('/proc/sys/net/ipv4/tcp_l3mdev_accept')
        self.assertIn(tmp, '1')
        tmp = read_file('/proc/sys/net/ipv4/udp_l3mdev_accept')
        self.assertIn(tmp, '1')

    def test_vrf_table_id_is_unalterable(self):
        # Linux Kernel prohibits the change of a VRF table  on the fly.
        # VRF must be deleted and recreated!
        table = '1000'
        vrf = vrfs[0]
        base = base_path + ['name', vrf]
        self.cli_set(base + ['table', table])

        # commit changes
        self.cli_commit()

        # Check if VRF has been created
        self.assertTrue(vrf in interfaces())

        table = str(int(table) + 1)
        self.cli_set(base + ['table', table])
        # check validate() - table ID can not be altered!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

    def test_vrf_assign_interface(self):
        vrf = vrfs[0]
        table = '5000'
        self.cli_set(['vrf', 'name', vrf, 'table', table])

        for interface in self._interfaces:
            section = Section.section(interface)
            self.cli_set(['interfaces', section, interface, 'vrf', vrf])

        # commit changes
        self.cli_commit()

        # Verify & cleanup
        for interface in self._interfaces:
            # os.readlink resolves to: '../../../../../virtual/net/foovrf'
            tmp = os.readlink(f'/sys/class/net/{interface}/master').split('/')[-1]
            self.assertEqual(tmp, vrf)
            # cleanup
            section = Section.section(interface)
            self.cli_delete(['interfaces', section, interface, 'vrf'])

    def test_vrf_static_route(self):
        table = '100'
        for vrf in vrfs:
            next_hop = f'192.0.{table}.1'
            prefix = f'10.0.{table}.0/24'
            base = base_path + ['name', vrf]

            self.cli_set(base + ['vni', table])

            # check validate() - a table ID is mandatory
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()

            self.cli_set(base + ['table', table])
            self.cli_set(base + ['protocols', 'static', 'route', prefix, 'next-hop', next_hop])

            table = str(int(table) + 1)

        # commit changes
        self.cli_commit()

        # Verify VRF configuration
        table = '100'
        for vrf in vrfs:
            next_hop = f'192.0.{table}.1'
            prefix = f'10.0.{table}.0/24'

            self.assertTrue(vrf in interfaces())
            vrf_if = Interface(vrf)

            frrconfig = self.getFRRconfig(f'vrf {vrf}')
            self.assertIn(f' vni {table}', frrconfig)
            self.assertIn(f' ip route {prefix} {next_hop}', frrconfig)

            # Increment table ID for the next run
            table = str(int(table) + 1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
