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

import unittest

from vyos.ifconfig import Interface
from vyos.utils.network import get_interface_config

from base_interfaces_test import BasicInterfaceTest

class GeneveInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'geneve']
        cls._options = {
            'gnv0': ['vni 10', 'remote 127.0.1.1'],
            'gnv1': ['vni 20', 'remote 127.0.1.2'],
            'gnv1': ['vni 30', 'remote 2001:db8::1', 'parameters ipv6 flowlabel 0x1000'],
        }
        cls._interfaces = list(cls._options)
        # call base-classes classmethod
        super(GeneveInterfaceTest, cls).setUpClass()

    def test_geneve_parameters(self):
        tos = '40'
        ttl = 20
        for intf in self._interfaces:
            for option in self._options.get(intf, []):
                self.cli_set(self._base_path + [intf] + option.split())

            self.cli_set(self._base_path + [intf, 'parameters', 'ip', 'df', 'set'])
            self.cli_set(self._base_path + [intf, 'parameters', 'ip', 'tos', tos])
            self.cli_set(self._base_path + [intf, 'parameters', 'ip', 'innerproto'])
            self.cli_set(self._base_path + [intf, 'parameters', 'ip', 'ttl', str(ttl)])
            ttl += 10

        self.cli_commit()

        ttl = 20
        for interface in self._interfaces:
            options = get_interface_config(interface)

            vni = options['linkinfo']['info_data']['id']
            self.assertIn(f'vni {vni}',       self._options[interface])

            if any('remote' in s for s in self._options[interface]):
                key = 'remote'
                if 'remote6' in options['linkinfo']['info_data']:
                    key = 'remote6'

                remote = options['linkinfo']['info_data'][key]
                self.assertIn(f'remote {remote}', self._options[interface])

            if any('flowlabel' in s for s in self._options[interface]):
                label = options['linkinfo']['info_data']['label']
                self.assertIn(f'parameters ipv6 flowlabel {label}', self._options[interface])

            if any('innerproto' in s for s in self._options[interface]):
                inner = options['linkinfo']['info_data']['innerproto']
                self.assertIn(f'parameters ip {inner}', self._options[interface])


            self.assertEqual('geneve',        options['linkinfo']['info_kind'])
            self.assertEqual('set',      options['linkinfo']['info_data']['df'])
            self.assertEqual(f'0x{tos}', options['linkinfo']['info_data']['tos'])
            self.assertEqual(ttl,        options['linkinfo']['info_data']['ttl'])
            self.assertEqual(Interface(interface).get_admin_state(), 'up')
            ttl += 10

if __name__ == '__main__':
    unittest.main(verbosity=2)
