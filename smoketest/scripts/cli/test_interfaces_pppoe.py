#!/usr/bin/env python3
#
# Copyright (C) 2019-2022 VyOS maintainers and contributors
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
import unittest

from psutil import process_iter
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError

config_file = '/etc/ppp/peers/{}'
base_path = ['interfaces', 'pppoe']

def get_config_value(interface, key):
    with open(config_file.format(interface), 'r') as f:
        for line in f:
            if line.startswith(key):
                return list(line.split())
    return []

# add a classmethod to setup a temporaray PPPoE server for "proper" validation
class PPPoEInterfaceTest(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(PPPoEInterfaceTest, cls).setUpClass()

        cls._interfaces = ['pppoe10', 'pppoe20', 'pppoe30']
        cls._source_interface = 'eth0'

    def tearDown(self):
        # Validate PPPoE client process
        for interface in self._interfaces:
            running = False
            for proc in process_iter():
                if interface in proc.cmdline():
                    running = True
                    break
            self.assertTrue(running)

        self.cli_delete(base_path)
        self.cli_commit()

    def test_01_pppoe_client(self):
        # Check if PPPoE dialer can be configured and runs
        for interface in self._interfaces:
            user = 'VyOS-user-' + interface
            passwd = 'VyOS-passwd-' + interface
            mtu = '1400'

            self.cli_set(base_path + [interface, 'authentication', 'user', user])
            self.cli_set(base_path + [interface, 'authentication', 'password', passwd])
            self.cli_set(base_path + [interface, 'mtu', mtu])
            self.cli_set(base_path + [interface, 'no-peer-dns'])

            # check validate() - a source-interface is required
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_set(base_path + [interface, 'source-interface', self._source_interface])

        # commit changes
        self.cli_commit()

        # verify configuration file(s)
        for interface in self._interfaces:
            user = 'VyOS-user-' + interface
            password = 'VyOS-passwd-' + interface

            tmp = get_config_value(interface, 'mtu')[1]
            self.assertEqual(tmp, mtu)
            tmp = get_config_value(interface, 'user')[1].replace('"', '')
            self.assertEqual(tmp, user)
            tmp = get_config_value(interface, 'password')[1].replace('"', '')
            self.assertEqual(tmp, password)
            tmp = get_config_value(interface, 'ifname')[1]
            self.assertEqual(tmp, interface)

    def test_02_pppoe_client_disabled_interface(self):
        # Check if PPPoE Client can be disabled
        for interface in self._interfaces:
            self.cli_set(base_path + [interface, 'authentication', 'user', 'vyos'])
            self.cli_set(base_path + [interface, 'authentication', 'password', 'vyos'])
            self.cli_set(base_path + [interface, 'source-interface', self._source_interface])
            self.cli_set(base_path + [interface, 'disable'])

        self.cli_commit()

        # Validate PPPoE client process - must not run as interfaces are disabled
        for interface in self._interfaces:
            running = False
            for proc in process_iter():
                if interface in proc.cmdline():
                    running = True
                    break
            self.assertFalse(running)

        # enable PPPoE interfaces
        for interface in self._interfaces:
            self.cli_delete(base_path + [interface, 'disable'])

        self.cli_commit()


    def test_03_pppoe_authentication(self):
        # When username or password is set - so must be the other
        for interface in self._interfaces:
            self.cli_set(base_path + [interface, 'authentication', 'user', 'vyos'])
            self.cli_set(base_path + [interface, 'source-interface', self._source_interface])
            self.cli_set(base_path + [interface, 'ipv6', 'address', 'autoconf'])

            # check validate() - if user is set, so must be the password
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()

            self.cli_set(base_path + [interface, 'authentication', 'password', 'vyos'])

        self.cli_commit()

    def test_04_pppoe_dhcpv6pd(self):
        # Check if PPPoE dialer can be configured with DHCPv6-PD
        address = '1'
        sla_id = '0'
        sla_len = '8'

        for interface in self._interfaces:
            self.cli_set(base_path + [interface, 'authentication', 'user', 'vyos'])
            self.cli_set(base_path + [interface, 'authentication', 'password', 'vyos'])
            self.cli_set(base_path + [interface, 'no-default-route'])
            self.cli_set(base_path + [interface, 'no-peer-dns'])
            self.cli_set(base_path + [interface, 'source-interface', self._source_interface])
            self.cli_set(base_path + [interface, 'ipv6', 'address', 'autoconf'])

            # prefix delegation stuff
            dhcpv6_pd_base = base_path + [interface, 'dhcpv6-options', 'pd', '0']
            self.cli_set(dhcpv6_pd_base + ['length', '56'])
            self.cli_set(dhcpv6_pd_base + ['interface', self._source_interface, 'address', address])
            self.cli_set(dhcpv6_pd_base + ['interface', self._source_interface, 'sla-id',  sla_id])

            # commit changes
            self.cli_commit()

            # verify "normal" PPPoE value - 1492 is default MTU
            tmp = get_config_value(interface, 'mtu')[1]
            self.assertEqual(tmp, '1492')
            tmp = get_config_value(interface, 'user')[1].replace('"', '')
            self.assertEqual(tmp, 'vyos')
            tmp = get_config_value(interface, 'password')[1].replace('"', '')
            self.assertEqual(tmp, 'vyos')
            tmp = get_config_value(interface, '+ipv6 ipv6cp-use-ipaddr')
            self.assertListEqual(tmp, ['+ipv6', 'ipv6cp-use-ipaddr'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
