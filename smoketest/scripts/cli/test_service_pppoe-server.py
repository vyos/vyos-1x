#!/usr/bin/env python3
#
# Copyright (C) 2022-2024 VyOS maintainers and contributors
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

from base_accel_ppp_test import BasicAccelPPPTest

from configparser import ConfigParser
from vyos.utils.file import read_file
from vyos.template import range_to_regex
from vyos.configsession import ConfigSessionError

local_if = ['interfaces', 'dummy', 'dum667']
ac_name = 'ACN'
interface = 'eth0'

class TestServicePPPoEServer(BasicAccelPPPTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['service', 'pppoe-server']
        cls._config_file = '/run/accel-pppd/pppoe.conf'
        cls._chap_secrets = '/run/accel-pppd/pppoe.chap-secrets'
        cls._protocol_section = 'pppoe'
        # call base-classes classmethod
        super(TestServicePPPoEServer, cls).setUpClass()

    def tearDown(self):
        self.cli_delete(local_if)
        super().tearDown()

    def verify(self, conf):
        mtu = '1492'

        # validate some common values in the configuration
        for tmp in ['log_syslog', 'pppoe', 'ippool',
                    'auth_mschap_v2', 'auth_mschap_v1', 'auth_chap_md5',
                    'auth_pap', 'shaper']:
            # Settings without values provide None
            self.assertEqual(conf['modules'][tmp], None)

        # check Access Concentrator setting
        self.assertTrue(conf['pppoe']['ac-name'] == ac_name)
        self.assertTrue(conf['pppoe'].getboolean('verbose'))
        self.assertTrue(conf['pppoe']['interface'], interface)

        # check ppp
        self.assertTrue(conf['ppp'].getboolean('verbose'))
        self.assertTrue(conf['ppp'].getboolean('check-ip'))
        self.assertEqual(conf['ppp']['mtu'], mtu)

        super().verify(conf)

    def basic_protocol_specific_config(self):
        self.cli_set(local_if + ['address', '192.0.2.1/32'])
        self.set(['access-concentrator', ac_name])
        self.set(['interface', interface])

    def test_pppoe_limits(self):
        self.basic_config()
        self.set(['limits', 'connection-limit', '20/min'])
        self.cli_commit()
        conf = ConfigParser(allow_no_value=True, delimiters='=')
        conf.read(self._config_file)
        self.assertEqual(conf['connlimit']['limit'], '20/min')

    def test_pppoe_server_authentication_protocols(self):
        # Test configuration of local authentication for PPPoE server
        self.basic_config()

        # explicitly test mschap-v2 - no special reason
        self.set( ['authentication', 'protocols', 'mschap-v2'])

        # commit changes
        self.cli_commit()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True)
        conf.read(self._config_file)

        self.assertEqual(conf['modules']['auth_mschap_v2'], None)

    def test_pppoe_server_shaper(self):
        fwmark = '223'
        limiter = 'tbf'
        self.basic_config()

        self.set(['shaper', 'fwmark', fwmark])
        # commit changes

        self.cli_commit()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True, delimiters='=')
        conf.read(self._config_file)

        # basic verification
        self.verify(conf)

        self.assertEqual(conf['shaper']['fwmark'], fwmark)
        self.assertEqual(conf['shaper']['down-limiter'], limiter)

    def test_accel_radius_authentication(self):
        radius_called_sid = 'ifname:mac'

        self.set(['authentication', 'radius', 'called-sid-format', radius_called_sid])

        # run common tests
        super().test_accel_radius_authentication()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True, delimiters='=')
        conf.read(self._config_file)

        # Validate configuration
        self.assertEqual(conf['pppoe']['called-sid'], radius_called_sid)

    def test_pppoe_server_vlan(self):

        vlans = ['100', '200', '300-310']

        # Test configuration of local authentication for PPPoE server
        self.basic_config()

        self.set(['interface', interface, 'vlan-mon'])

        # cannot use option "vlan-mon" if no "vlan" set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        for vlan in vlans:
            self.set(['interface', interface, 'vlan', vlan])

        # commit changes
        self.cli_commit()

        # Validate configuration values
        config = read_file(self._config_file)
        for vlan in vlans:
            tmp = range_to_regex(vlan)
            self.assertIn(f'interface=re:^{interface}\.{tmp}$', config)

        tmp = ','.join(vlans)
        self.assertIn(f'vlan-mon={interface},{tmp}', config)

    def test_pppoe_server_pado_delay(self):
        delay_without_sessions = '10'
        delays = {'20': '200', '30': '300'}

        self.basic_config()

        self.set(['pado-delay', delay_without_sessions])
        self.cli_commit()

        conf = ConfigParser(allow_no_value=True, delimiters='=')
        conf.read(self._config_file)
        self.assertEqual(conf['pppoe']['pado-delay'], delay_without_sessions)

        for delay, sessions in delays.items():
            self.set(['pado-delay', delay, 'sessions', sessions])
        self.cli_commit()

        conf = ConfigParser(allow_no_value=True, delimiters='=')
        conf.read(self._config_file)

        self.assertEqual(conf['pppoe']['pado-delay'], '10,20:200,30:300')

        self.set(['pado-delay', 'disable', 'sessions', '400'])
        self.cli_commit()

        conf = ConfigParser(allow_no_value=True, delimiters='=')
        conf.read(self._config_file)
        self.assertEqual(conf['pppoe']['pado-delay'], '10,20:200,30:300,-1:400')

    def test_pppoe_server_any_login(self):
        # Test configuration of local authentication for PPPoE server
        self.basic_config()

        self.set(['authentication', 'any-login'])
        self.cli_commit()

        # Validate configuration values
        config = read_file(self._config_file)
        self.assertIn('any-login=1', config)

    def test_pppoe_server_accept_service(self):
        services = ['user1-service', 'user2-service']
        self.basic_config()

        for service in services:
            self.set(['service-name', service])
        self.set(['accept-any-service'])
        self.set(['accept-blank-service'])
        self.cli_commit()

        # Validate configuration values
        config = read_file(self._config_file)
        self.assertIn(f'service-name={",".join(services)}', config)
        self.assertIn('accept-any-service=1', config)
        self.assertIn('accept-blank-service=1', config)


if __name__ == '__main__':
    unittest.main(verbosity=2)
