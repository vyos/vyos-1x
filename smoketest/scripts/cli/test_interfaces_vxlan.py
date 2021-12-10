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

import unittest

from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Interface
from vyos.util import get_interface_config

from base_interfaces_test import BasicInterfaceTest

class VXLANInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._test_ip = True
        cls._test_ipv6 = True
        cls._test_mtu = True
        cls._base_path = ['interfaces', 'vxlan']
        cls._options = {
            'vxlan10': ['vni 10', 'remote 127.0.0.2'],
            'vxlan20': ['vni 20', 'group 239.1.1.1', 'source-interface eth0'],
            'vxlan30': ['vni 30', 'remote 2001:db8:2000::1', 'source-address 2001:db8:1000::1', 'parameters ipv6 flowlabel 0x1000'],
        }
        cls._interfaces = list(cls._options)
        # call base-classes classmethod
        super(cls, cls).setUpClass()

    def test_vxlan_parameters(self):
        tos = '40'
        ttl = 20
        for intf in self._interfaces:
            for option in self._options.get(intf, []):
                self.cli_set(self._base_path + [intf] + option.split())

            self.cli_set(self._base_path + [intf, 'parameters', 'ip', 'dont-fragment'])
            self.cli_set(self._base_path + [intf, 'parameters', 'ip', 'tos', tos])
            self.cli_set(self._base_path + [intf, 'parameters', 'ip', 'ttl', str(ttl)])
            ttl += 10

        self.cli_commit()

        ttl = 20
        for interface in self._interfaces:
            options = get_interface_config(interface)

            vni = options['linkinfo']['info_data']['id']
            self.assertIn(f'vni {vni}', self._options[interface])

            if any('link' in s for s in self._options[interface]):
                link = options['linkinfo']['info_data']['link']
                self.assertIn(f'source-interface {link}', self._options[interface])

            if any('local6' in s for s in self._options[interface]):
                remote = options['linkinfo']['info_data']['local6']
                self.assertIn(f'source-address {local6}', self._options[interface])

            if any('remote6' in s for s in self._options[interface]):
                remote = options['linkinfo']['info_data']['remote6']
                self.assertIn(f'remote {remote}', self._options[interface])

            if any('group' in s for s in self._options[interface]):
                group = options['linkinfo']['info_data']['group']
                self.assertIn(f'group {group}', self._options[interface])

            if any('flowlabel' in s for s in self._options[interface]):
                label = options['linkinfo']['info_data']['label']
                self.assertIn(f'parameters ipv6 flowlabel {label}', self._options[interface])

            if any('external' in s for s in self._options[interface]):
                self.assertTrue(options['linkinfo']['info_data']['external'])

            self.assertEqual('vxlan',    options['linkinfo']['info_kind'])
            self.assertEqual('set',      options['linkinfo']['info_data']['df'])
            self.assertEqual(f'0x{tos}', options['linkinfo']['info_data']['tos'])
            self.assertEqual(ttl,        options['linkinfo']['info_data']['ttl'])
            self.assertEqual(Interface(interface).get_admin_state(), 'up')
            ttl += 10

    def test_vxlan_external(self):
        interface = 'vxlan0'
        source_address = '192.0.2.1'
        self.cli_set(self._base_path + [interface, 'external'])
        self.cli_set(self._base_path + [interface, 'source-address', source_address])

        # Both 'VNI' and 'external' can not be specified at the same time.
        self.cli_set(self._base_path + [interface, 'vni', '111'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(self._base_path + [interface, 'vni'])

        # Now add some more interfaces - this must fail and a CLI error needs
        # to be generated as Linux can only handle one VXLAN tunnel when using
        # external mode.
        for intf in self._interfaces:
            for option in self._options.get(intf, []):
                self.cli_set(self._base_path + [intf] + option.split())
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # Remove those test interfaces again
        for intf in self._interfaces:
            self.cli_delete(self._base_path + [intf])

        self.cli_commit()

        options = get_interface_config(interface)
        self.assertTrue(options['linkinfo']['info_data']['external'])
        self.assertEqual('vxlan',    options['linkinfo']['info_kind'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
