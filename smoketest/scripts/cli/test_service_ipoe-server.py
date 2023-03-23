#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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

from base_accel_ppp_test import BasicAccelPPPTest
from vyos.configsession import ConfigSessionError
from vyos.util import cmd

from configparser import ConfigParser

ac_name = 'ACN'
interface = 'eth0'


def getConfig(string, end='cli'):
    command = f'cat /run/accel-pppd/ipoe.conf | sed -n "/^{string}/,/^{end}/p"'
    out = cmd(command)
    return out


class TestServiceIPoEServer(BasicAccelPPPTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['service', 'ipoe-server']
        cls._config_file = '/run/accel-pppd/ipoe.conf'
        cls._chap_secrets = '/run/accel-pppd/ipoe.chap-secrets'

        # call base-classes classmethod
        super(TestServiceIPoEServer, cls).setUpClass()

    def verify(self, conf):
        super().verify(conf)

        # Validate configuration values
        accel_modules = list(conf['modules'].keys())
        self.assertIn('log_syslog', accel_modules)
        self.assertIn('ipoe', accel_modules)
        self.assertIn('shaper', accel_modules)
        self.assertIn('ipv6pool', accel_modules)
        self.assertIn('ipv6_nd', accel_modules)
        self.assertIn('ipv6_dhcp', accel_modules)
        self.assertIn('ippool', accel_modules)

    def basic_config(self):
        self.set(['interface', interface, 'client-subnet', '192.168.0.0/24'])

    def test_accel_local_authentication(self):
        mac_address = '08:00:27:2f:d8:06'
        self.set(['authentication', 'interface', interface, 'mac', mac_address])
        self.set(['authentication', 'mode', 'local'])

        # No IPoE interface configured
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # Test configuration of local authentication for PPPoE server
        self.basic_config()

        # commit changes
        self.cli_commit()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True, delimiters='=')
        conf.read(self._config_file)

        # check proper path to chap-secrets file
        self.assertEqual(conf['chap-secrets']['chap-secrets'], self._chap_secrets)

        accel_modules = list(conf['modules'].keys())
        self.assertIn('chap-secrets', accel_modules)

        # basic verification
        self.verify(conf)

        # check local users
        tmp = cmd(f'sudo cat {self._chap_secrets}')
        regex = f'{interface}\s+\*\s+{mac_address}\s+\*'
        tmp = re.findall(regex, tmp)
        self.assertTrue(tmp)

    def test_accel_named_pool(self):
        first_pool = 'VyOS-pool1'
        first_subnet = '192.0.2.0/25'
        first_gateway = '192.0.2.1'
        second_pool = 'Vyos-pool2'
        second_subnet = '203.0.113.0/25'
        second_gateway = '203.0.113.1'

        self.set(['authentication', 'mode', 'noauth'])
        self.set(['client-ip-pool', 'name', first_pool, 'gateway-address', first_gateway])
        self.set(['client-ip-pool', 'name', first_pool, 'subnet', first_subnet])
        self.set(['client-ip-pool', 'name', second_pool, 'gateway-address', second_gateway])
        self.set(['client-ip-pool', 'name', second_pool, 'subnet', second_subnet])
        self.set(['interface', interface])

        # commit changes
        self.cli_commit()


        # Validate configuration values
        conf = ConfigParser(allow_no_value=True, delimiters='=', strict=False)
        conf.read(self._config_file)

        self.assertTrue(conf['ipoe']['interface'], f'{interface},shared=1,mode=L2,ifcfg=1,start=dhcpv4,ipv6=1')
        self.assertTrue(conf['ipoe']['noauth'], '1')
        self.assertTrue(conf['ipoe']['ip-pool'], first_pool)
        self.assertTrue(conf['ipoe']['ip-pool'], second_pool)
        self.assertTrue(conf['ipoe']['gw-ip-address'], f'{first_gateway}/25')
        self.assertTrue(conf['ipoe']['gw-ip-address'], f'{second_gateway}/25')

        config = getConfig('[ip-pool]')
        pool_config = f'''{second_subnet},name={second_pool}
{first_subnet},name={first_pool}
gw-ip-address={second_gateway}/25
gw-ip-address={first_gateway}/25'''
        self.assertIn(pool_config, config)


    def test_accel_next_pool(self):
        first_pool = 'VyOS-pool1'
        first_subnet = '192.0.2.0/25'
        first_gateway = '192.0.2.1'
        second_pool = 'Vyos-pool2'
        second_subnet = '203.0.113.0/25'
        second_gateway = '203.0.113.1'
        third_pool = 'Vyos-pool3'
        third_subnet = '198.51.100.0/24'
        third_gateway = '198.51.100.1'

        self.set(['authentication', 'mode', 'noauth'])
        self.set(['client-ip-pool', 'name', first_pool, 'gateway-address', first_gateway])
        self.set(['client-ip-pool', 'name', first_pool, 'subnet', first_subnet])
        self.set(['client-ip-pool', 'name', first_pool, 'next-pool', second_pool])
        self.set(['client-ip-pool', 'name', second_pool, 'gateway-address', second_gateway])
        self.set(['client-ip-pool', 'name', second_pool, 'subnet', second_subnet])
        self.set(['client-ip-pool', 'name', second_pool, 'next-pool', third_pool])
        self.set(['client-ip-pool', 'name', third_pool, 'gateway-address', third_gateway])
        self.set(['client-ip-pool', 'name', third_pool, 'subnet', third_subnet])
        self.set(['interface', interface])

        # commit changes
        self.cli_commit()


        # Validate configuration values
        conf = ConfigParser(allow_no_value=True, delimiters='=', strict=False)
        conf.read(self._config_file)

        self.assertTrue(conf['ipoe']['interface'], f'{interface},shared=1,mode=L2,ifcfg=1,start=dhcpv4,ipv6=1')
        self.assertTrue(conf['ipoe']['noauth'], '1')
        self.assertTrue(conf['ipoe']['ip-pool'], first_pool)
        self.assertTrue(conf['ipoe']['gw-ip-address'], f'{first_gateway}/25')
        self.assertTrue(conf['ipoe']['gw-ip-address'], f'{second_gateway}/25')
        self.assertTrue(conf['ipoe']['gw-ip-address'], f'{third_gateway}/24')

        config = getConfig('[ip-pool]')
        # T5099 required specific order
        pool_config = f'''{third_subnet},name={third_pool}
{second_subnet},name={second_pool},next={third_pool}
{first_subnet},name={first_pool},next={second_pool}
gw-ip-address={third_gateway}/24
gw-ip-address={second_gateway}/25
gw-ip-address={first_gateway}/25'''
        self.assertIn(pool_config, config)


if __name__ == '__main__':
    unittest.main(verbosity=2)

