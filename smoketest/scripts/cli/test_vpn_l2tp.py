#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
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
from configparser import ConfigParser
from vyos.utils.process import cmd


class TestVPNL2TPServer(BasicAccelPPPTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['vpn', 'l2tp', 'remote-access']
        cls._config_file = '/run/accel-pppd/l2tp.conf'
        cls._chap_secrets = '/run/accel-pppd/l2tp.chap-secrets'
        cls._protocol_section = 'l2tp'
        # call base-classes classmethod
        super(TestVPNL2TPServer, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(TestVPNL2TPServer, cls).tearDownClass()

    def basic_protocol_specific_config(self):
        pass

    def test_l2tp_server_ppp_options(self):
        # Test configuration of local authentication for PPPoE server
        self.basic_config()
        mtu = '1425'
        lcp_echo_failure = '5'
        lcp_echo_interval = '40'
        lcp_echo_timeout = '3000'
        # other settings
        mppe = 'require'
        self.set(['ccp-disable'])
        self.set(['ppp-options', 'mppe', mppe])
        self.set(['authentication', 'radius', 'preallocate-vif'])
        self.set(['mtu', mtu])
        self.set(['ppp-options', 'lcp-echo-failure', lcp_echo_failure])
        self.set(['ppp-options', 'lcp-echo-interval', lcp_echo_interval])
        self.set(['ppp-options', 'lcp-echo-timeout', lcp_echo_timeout])

        allow_ipv6 = 'allow'
        random = 'random'
        self.set(['ppp-options', 'ipv6', allow_ipv6])
        self.set(['ppp-options', 'ipv6-intf-id', random])
        self.set(['ppp-options', 'ipv6-accept-peer-intf-id'])
        self.set(['ppp-options', 'ipv6-peer-intf-id', random])

        # commit changes
        self.cli_commit()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True, delimiters='=')
        conf.read(self._config_file)

        # basic verification
        self.verify(conf)

        # check ppp
        self.assertEqual(conf['ppp']['mppe'], mppe)
        self.assertFalse(conf['ppp'].getboolean('ccp'))
        self.assertEqual(conf['ppp']['unit-preallocate'], '1')
        self.assertTrue(conf['ppp'].getboolean('verbose'))
        self.assertTrue(conf['ppp'].getboolean('check-ip'))
        self.assertEqual(conf['ppp']['mtu'], mtu)
        self.assertEqual(conf['ppp']['lcp-echo-interval'], lcp_echo_interval)
        self.assertEqual(conf['ppp']['lcp-echo-timeout'], lcp_echo_timeout)
        self.assertEqual(conf['ppp']['lcp-echo-failure'], lcp_echo_failure)

        for tmp in ['ipv6pool', 'ipv6_nd', 'ipv6_dhcp']:
            self.assertEqual(conf['modules'][tmp], None)
        self.assertEqual(conf['ppp']['ipv6'], allow_ipv6)
        self.assertEqual(conf['ppp']['ipv6-intf-id'], random)
        self.assertEqual(conf['ppp']['ipv6-peer-intf-id'], random)
        self.assertTrue(conf['ppp'].getboolean('ipv6-accept-peer-intf-id'))

    def test_l2tp_server_authentication_protocols(self):
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
