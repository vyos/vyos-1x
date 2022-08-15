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

from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.util import process_named_running
from vyos.util import cmd
from vyos.util import read_file
from os import path, mkdir

base_path   = ['vpn', 'openconnect']
cert_dir    = '/config/auth/'
ca_cert     = f'{cert_dir}ca.crt'
ssl_cert    = f'{cert_dir}server.crt'
ssl_key     = f'{cert_dir}server.key'

PROCESS_NAME = 'ocserv-main'
config_file = '/run/ocserv/ocserv.conf'
auth_file = '/run/ocserv/ocpasswd'
otp_file = '/run/ocserv/users.oath'

class TestVPNOpenConnect(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestVPNOpenConnect, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

        cls.cli_set(cls, base_path + ["ssl", "ca-cert-file", ca_cert])
        cls.cli_set(cls, base_path + ["ssl", "cert-file", ssl_cert])
        cls.cli_set(cls, base_path + ["ssl", "key-file", ssl_key])

    def tearDown(self):
        self.assertTrue(process_named_running(PROCESS_NAME))

        # Delete vpn openconnect configuration
        self.cli_delete(base_path)
        self.cli_commit()

        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_ocserv(self):
        user = 'vyos_user'
        password = 'vyos_pass'

        v4_subnet = '192.0.2.0/24'
        v6_prefix = '2001:db8:1000::/64'
        v6_len = '126'
        name_server = ['1.2.3.4', '1.2.3.5', '2001:db8::1']

        self.cli_set(base_path + ['authentication', 'local-users', 'username', user, 'password', password])
        self.cli_set(base_path + ['authentication', 'mode', "local"])
        self.cli_set(base_path + ["network-settings", "client-ip-settings", "subnet", v4_subnet])
        self.cli_set(base_path + ['network-settings', 'client-ip-settings', 'subnet', v4_subnet])
        self.cli_set(base_path + ['network-settings', 'client-ipv6-pool', 'prefix', v6_prefix])
        self.cli_set(base_path + ['network-settings', 'client-ipv6-pool', 'mask', v6_len])

        for ns in name_server:
            self.cli_set(base_path + ['network-settings', 'name-server', ns])

        self.cli_commit()

        # Verify configuration
        daemon_config = read_file(config_file)

        # authentication mode local password-otp
        self.assertIn(f'auth = "plain[/run/ocserv/ocpasswd]"', daemon_config)
        self.assertIn(f'ipv4-network = {v4_subnet}', daemon_config)
        self.assertIn(f'ipv6-network = {v6_prefix}', daemon_config)
        self.assertIn(f'ipv6-subnet-prefix = {v6_len}', daemon_config)

        for ns in name_server:
            self.assertIn(f'dns = {ns}', daemon_config)

        auth_config = read_file(auth_file)
        self.assertIn(f'{user}:*:$', auth_config)

if __name__ == '__main__':
    if not path.exists(cert_dir):
        mkdir(cert_dir)

    # Our SSL certificates need a subject ...
    subject = '/C=DE/ST=BY/O=VyOS/localityName=Cloud/commonName=vyos/' \
              'organizationalUnitName=VyOS/emailAddress=maintainers@vyos.io/'

    # Generate mandatory SSL certificate
    tmp = f'openssl req -newkey rsa:4096 -new -nodes -x509 -days 3650 '\
          f'-keyout {ssl_key} -out {ssl_cert} -subj {subject}'
    cmd(tmp)

    # Generate "CA"
    tmp = f'openssl req -new -x509 -key {ssl_key} -out {ca_cert} '\
          f'-subj {subject}'
    cmd(tmp)

    unittest.main(verbosity=2)
