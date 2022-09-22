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

if __name__ == '__main__':
    unittest.main(verbosity=2)

