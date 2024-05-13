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
        # Test configuration of local authentication protocols
        self.basic_config()

        # explicitly test mschap-v2 - no special reason
        self.set( ['authentication', 'protocols', 'mschap-v2'])

        # commit changes
        self.cli_commit()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True)
        conf.read(self._config_file)

        self.assertEqual(conf['modules']['auth_mschap_v2'], None)

    def test_vpn_l2tp_dependence_ipsec_swanctl(self):
        # Test config vpn for tasks T3843 and T5926

        base_path = ['vpn', 'l2tp', 'remote-access']
        # make precondition
        self.cli_set(['interfaces', 'dummy', 'dum0', 'address', '203.0.113.1/32'])
        self.cli_set(['vpn', 'ipsec', 'interface', 'dum0'])

        self.cli_commit()
        # check ipsec apply to swanctl
        self.assertEqual('', cmd('echo vyos | sudo -S swanctl -L '))

        self.cli_set(base_path + ['authentication', 'local-users', 'username', 'foo', 'password', 'bar'])
        self.cli_set(base_path + ['authentication', 'mode', 'local'])
        self.cli_set(base_path + ['authentication', 'protocols', 'chap'])
        self.cli_set(base_path + ['client-ip-pool', 'first', 'range', '10.200.100.100-10.200.100.110'])
        self.cli_set(base_path + ['description', 'VPN - REMOTE'])
        self.cli_set(base_path + ['name-server', '1.1.1.1'])
        self.cli_set(base_path + ['ipsec-settings', 'authentication', 'mode', 'pre-shared-secret'])
        self.cli_set(base_path + ['ipsec-settings', 'authentication', 'pre-shared-secret', 'SeCret'])
        self.cli_set(base_path + ['ipsec-settings', 'ike-lifetime', '8600'])
        self.cli_set(base_path + ['ipsec-settings', 'lifetime', '3600'])
        self.cli_set(base_path + ['outside-address', '203.0.113.1'])
        self.cli_set(base_path + ['gateway-address', '203.0.113.1'])

        self.cli_commit()

        # check l2tp apply to swanctl
        self.assertTrue('l2tp_remote_access:' in cmd('echo vyos | sudo -S swanctl -L '))

        self.cli_delete(['vpn', 'l2tp'])
        self.cli_commit()

        # check l2tp apply to swanctl after delete config
        self.assertEqual('', cmd('echo vyos | sudo -S swanctl -L '))

        # need to correct tearDown test
        self.basic_config()
        self.cli_set(base_path + ['authentication', 'protocols', 'chap'])
        self.cli_commit()

    def test_l2tp_radius_server(self):
        base_path = ['vpn', 'l2tp', 'remote-access']
        radius_server = "192.0.2.22"
        radius_key = "secretVyOS"

        self.cli_set(base_path + ['authentication', 'mode', 'radius'])
        self.cli_set(base_path + ['gateway-address', '192.0.2.1'])
        self.cli_set(base_path + ['client-ip-pool', 'SIMPLE-POOL', 'range', '192.0.2.0/24'])
        self.cli_set(base_path + ['default-pool', 'SIMPLE-POOL'])
        self.cli_set(base_path + ['authentication', 'radius', 'server', radius_server, 'key', radius_key])
        self.cli_set(base_path + ['authentication', 'radius', 'server', radius_server, 'priority', '10'])
        self.cli_set(base_path + ['authentication', 'radius', 'server', radius_server, 'backup'])

        # commit changes
        self.cli_commit()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True)
        conf.read(self._config_file)
        server = conf["radius"]["server"].split(",")
        self.assertIn('weight=10', server)
        self.assertIn('backup', server)


if __name__ == '__main__':
    unittest.main(verbosity=2)
