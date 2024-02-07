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

    def test_l2tp_config_apply_ipsec(self):
        # preset configuration
        self.basic_config(is_gateway=False, is_client_pool=False)
        self.cli_set(['interfaces', 'dummy', 'dum0', 'address', '203.0.113.1/32'])
        self.cli_set(['vpn', 'ipsec', 'interface', 'eth0'])
        self.cli_commit()

        # verify strongSwan is not configured
        self.assertEqual('', cmd('sudo swanctl -L'))

        # set l2tp configuration
        self.set(['authentication', 'local-users', 'username', 'alice', 'password', 'notsecure'])
        self.set(['authentication', 'mode', 'local'])
        self.set(['client-ip-pool', 'test', 'range', '10.1.1.0/24'])
        self.set(['gateway-address', '10.1.1.1'])
        self.set(['ipsec-settings', 'authentication', 'mode', 'pre-shared-secret'])
        self.set(['ipsec-settings', 'authentication', 'pre-shared-secret', 'not-so-secret'])
        self.set(['outside-address', '192.168.1.1'])

        self.cli_commit()

        # verify ipsec configuration of l2tp was added to swanctl
        self.assertIn('l2tp_remote_access' in cmd('sudo swanctl -L'))

        # delete configuration
        self.delete([])
        self.cli_commit()

        # verify configuration was deleted from swanctl
        self.assertEqual('', cmd('sudo swanctl -L'))

        # for tearDown test
        self.basic_config()
        self.cli_commit()


if __name__ == '__main__':
    unittest.main(verbosity=2)
