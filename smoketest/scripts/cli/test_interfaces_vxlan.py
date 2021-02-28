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

from vyos.configsession import ConfigSession
from vyos.ifconfig import Interface
from vyos.util import get_json_iface_options

from base_interfaces_test import BasicInterfaceTest

class VXLANInterfaceTest(BasicInterfaceTest.BaseTest):
    @classmethod
    def setUpClass(cls):
        cls._test_ip = True
        cls._test_ipv6 = True
        cls._test_mtu = True
        cls._base_path = ['interfaces', 'vxlan']
        cls._options = {
            'vxlan10': ['vni 10', 'remote 127.0.0.2'],
            'vxlan20': ['vni 20', 'group 239.1.1.1', 'source-interface eth0'],
            'vxlan30': ['vni 30', 'remote 2001:db8:2000::1', 'source-address 2001:db8:1000::1'],
        }
        cls._interfaces = list(cls._options)

    def test_vxlan_parameters(self):
        addr = '192.0.2.0/31'
        tos = '40'
        ttl = 20
        for intf in self._interfaces:
            self.session.set(self._base_path + [intf, 'address', addr])
            for option in self._options.get(intf, []):
                self.session.set(self._base_path + [intf] + option.split())

            self.session.set(self._base_path + [intf, 'parameters', 'ip', 'dont-fragment'])
            self.session.set(self._base_path + [intf, 'parameters', 'ip', 'tos', tos])
            self.session.set(self._base_path + [intf, 'parameters', 'ip', 'ttl', str(ttl)])
            ttl += 10

        self.session.commit()

        ttl = 20
        for interface in self._interfaces:
            options = get_json_iface_options(interface)
            self.assertEqual('set',      options['linkinfo']['info_data']['df'])
            self.assertEqual(f'0x{tos}', options['linkinfo']['info_data']['tos'])
            self.assertEqual(ttl,        options['linkinfo']['info_data']['ttl'])
            self.assertEqual(Interface(interface).get_admin_state(), 'up')
            ttl += 10

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
