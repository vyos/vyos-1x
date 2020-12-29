#!/usr/bin/env python3
#
# Copyright (C) 020 VyOS maintainers and contributors
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

import os
import unittest

from base_accel_ppp_test import BasicAccelPPPTest

from configparser import ConfigParser
from vyos.configsession import ConfigSessionError
from vyos.util import process_named_running

local_if = ['interfaces', 'dummy', 'dum667']
ac_name = 'ACN'
interface = 'eth0'

class TestServicePPPoEServer(BasicAccelPPPTest.BaseTest):
    def setUp(self):
        self._base_path = ['service', 'pppoe-server']
        self._process_name = 'accel-pppd'
        self._config_file = '/run/accel-pppd/pppoe.conf'
        self._chap_secrets = '/run/accel-pppd/pppoe.chap-secrets'

        super().setUp()

    def tearDown(self):
        self.session.delete(local_if)
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
        self.assertEqual(conf['ppp']['lcp-echo-interval'], '30')
        self.assertEqual(conf['ppp']['lcp-echo-timeout'], '0')
        self.assertEqual(conf['ppp']['lcp-echo-failure'], '3')

        super().verify(conf)

    def basic_config(self):
        self.session.set(local_if + ['address', '192.0.2.1/32'])

        self.set(['access-concentrator', ac_name])
        self.set(['interface', interface])

        super().basic_config()

    def test_pppoe_server_ppp_options(self):
        # Test configuration of local authentication for PPPoE server
        self.basic_config()

        # other settings
        mppe = 'require'
        self.set(['ppp-options', 'ccp'])
        self.set(['ppp-options', 'mppe', mppe])
        self.set(['limits', 'connection-limit', '20/min'])

        # min-mtu
        min_mtu = '1400'
        self.set(['ppp-options', 'min-mtu', min_mtu])

        # mru
        mru = '9000'
        self.set(['ppp-options', 'mru', mru])

        # commit changes
        self.session.commit()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True, delimiters='=')
        conf.read(self._config_file)

        # basic verification
        self.verify(conf)

        self.assertEqual(conf['chap-secrets']['gw-ip-address'], self._gateway)

        # check ppp
        self.assertEqual(conf['ppp']['mppe'], mppe)
        self.assertEqual(conf['ppp']['min-mtu'], min_mtu)
        self.assertEqual(conf['ppp']['mru'], mru)

        self.assertTrue(conf['ppp'].getboolean('ccp'))

        # check other settings
        self.assertEqual(conf['connlimit']['limit'], '20/min')

        # Check for running process
        self.assertTrue(process_named_running(self._process_name))

    def test_pppoe_server_authentication_protocols(self):
        # Test configuration of local authentication for PPPoE server
        self.basic_config()

        # explicitly test mschap-v2 - no special reason
        self.set( ['authentication', 'protocols', 'mschap-v2'])

        # commit changes
        self.session.commit()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True)
        conf.read(self._config_file)

        self.assertEqual(conf['modules']['auth_mschap_v2'], None)

        # Check for running process
        self.assertTrue(process_named_running(self._process_name))

    def test_pppoe_server_client_ip_pool(self):
        # Test configuration of IPv6 client pools
        self.basic_config()

        subnet = '172.18.0.0/24'
        self.set(['client-ip-pool', 'subnet', subnet])

        start = '192.0.2.10'
        stop = '192.0.2.20'
        start_stop = f'{start}-{stop}'
        self.set(['client-ip-pool', 'start', start])
        self.set(['client-ip-pool', 'stop', stop])

        # commit changes
        self.session.commit()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True)
        conf.read(self._config_file)

        # check configured subnet
        self.assertEqual(conf['ip-pool'][subnet], None)
        self.assertEqual(conf['ip-pool'][start_stop], None)
        self.assertEqual(conf['ip-pool']['gw-ip-address'], self._gateway)

        # Check for running process
        self.assertTrue(process_named_running(self._process_name))


    def test_pppoe_server_client_ipv6_pool(self):
        # Test configuration of IPv6 client pools
        self.basic_config()

        # Enable IPv6
        allow_ipv6 = 'allow'
        random = 'random'
        self.set(['ppp-options', 'ipv6', allow_ipv6])
        self.set(['ppp-options', 'ipv6-intf-id', random])
        self.set(['ppp-options', 'ipv6-accept-peer-intf-id'])
        self.set(['ppp-options', 'ipv6-peer-intf-id', random])

        prefix = '2001:db8:ffff::/64'
        prefix_mask = '128'
        client_prefix = f'{prefix},{prefix_mask}'
        self.set(['client-ipv6-pool', 'prefix', prefix, 'mask', prefix_mask])

        delegate_prefix = '2001:db8::/40'
        delegate_mask = '56'
        self.set(['client-ipv6-pool', 'delegate', delegate_prefix, 'delegation-prefix', delegate_mask])

        # commit changes
        self.session.commit()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True, delimiters='=')
        conf.read(self._config_file)

        for tmp in ['ipv6pool', 'ipv6_nd', 'ipv6_dhcp']:
            self.assertEqual(conf['modules'][tmp], None)

        self.assertEqual(conf['ppp']['ipv6'], allow_ipv6)
        self.assertEqual(conf['ppp']['ipv6-intf-id'], random)
        self.assertEqual(conf['ppp']['ipv6-peer-intf-id'], random)
        self.assertTrue(conf['ppp'].getboolean('ipv6-accept-peer-intf-id'))

        self.assertEqual(conf['ipv6-pool'][client_prefix], None)
        self.assertEqual(conf['ipv6-pool']['delegate'], f'{delegate_prefix},{delegate_mask}')

        # Check for running process
        self.assertTrue(process_named_running(self._process_name))


    def test_accel_radius_authentication(self):
        radius_called_sid = 'ifname:mac'
        radius_acct_interim_jitter = '9'

        self.set(['authentication', 'radius', 'called-sid-format', radius_called_sid])
        self.set(['authentication', 'radius', 'acct-interim-jitter', radius_acct_interim_jitter])

        # run common tests
        super().test_accel_radius_authentication()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True, delimiters='=')
        conf.read(self._config_file)

        # Validate configuration
        self.assertEqual(conf['pppoe']['called-sid'], radius_called_sid)
        self.assertEqual(conf['radius']['acct-interim-jitter'], radius_acct_interim_jitter)


if __name__ == '__main__':
    unittest.main(verbosity=2)
