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
from vyos.util import read_file

OCSERV_CONF = '/run/ocserv/ocserv.conf'
base_path = ['vpn', 'openconnect']

pki_path = ['pki']

cert_data = """
MIICFDCCAbugAwIBAgIUfMbIsB/ozMXijYgUYG80T1ry+mcwCgYIKoZIzj0EAwIw
WTELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNv
bWUtQ2l0eTENMAsGA1UECgwEVnlPUzESMBAGA1UEAwwJVnlPUyBUZXN0MB4XDTIx
MDcyMDEyNDUxMloXDTI2MDcxOTEyNDUxMlowWTELMAkGA1UEBhMCR0IxEzARBgNV
BAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNvbWUtQ2l0eTENMAsGA1UECgwEVnlP
UzESMBAGA1UEAwwJVnlPUyBUZXN0MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE
01HrLcNttqq4/PtoMua8rMWEkOdBu7vP94xzDO7A8C92ls1v86eePy4QllKCzIw3
QxBIoCuH2peGRfWgPRdFsKNhMF8wDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8E
BAMCAYYwHQYDVR0lBBYwFAYIKwYBBQUHAwIGCCsGAQUFBwMBMB0GA1UdDgQWBBSu
+JnU5ZC4mkuEpqg2+Mk4K79oeDAKBggqhkjOPQQDAgNHADBEAiBEFdzQ/Bc3Lftz
ngrY605UhA6UprHhAogKgROv7iR4QgIgEFUxTtW3xXJcnUPWhhUFhyZoqfn8dE93
+dm/LDnp7C0=
"""

key_data = """
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgPLpD0Ohhoq0g4nhx
2KMIuze7ucKUt/lBEB2wc03IxXyhRANCAATTUestw222qrj8+2gy5rysxYSQ50G7
u8/3jHMM7sDwL3aWzW/zp54/LhCWUoLMjDdDEEigK4fal4ZF9aA9F0Ww
"""

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

        cls.cli_set(cls, pki_path + ['ca', 'openconnect', 'certificate', cert_data.replace('\n','')])
        cls.cli_set(cls, pki_path + ['certificate', 'openconnect', 'certificate', cert_data.replace('\n','')])
        cls.cli_set(cls, pki_path + ['certificate', 'openconnect', 'private', 'key', key_data.replace('\n','')])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, pki_path)
        super(TestVPNOpenConnect, cls).tearDownClass()

    def tearDown(self):
        self.assertTrue(process_named_running(PROCESS_NAME))

        self.cli_delete(base_path)
        self.cli_commit()

        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_ocserv(self):
        user = 'vyos_user'
        password = 'vyos_pass'
        otp = '37500000026900000000200000000000'
        v4_subnet = '192.0.2.0/24'
        v6_prefix = '2001:db8:1000::/64'
        v6_len = '126'
        name_server = ['1.2.3.4', '1.2.3.5', '2001:db8::1']
        split_dns = ['vyos.net', 'vyos.io']

        self.cli_set(base_path + ['authentication', 'local-users', 'username', user, 'password', password])
        self.cli_set(base_path + ['authentication', 'local-users', 'username', user, 'otp', 'key', otp])
        self.cli_set(base_path + ['authentication', 'mode', 'local', 'password-otp'])

        self.cli_set(base_path + ['network-settings', 'client-ip-settings', 'subnet', v4_subnet])
        self.cli_set(base_path + ['network-settings', 'client-ipv6-pool', 'prefix', v6_prefix])
        self.cli_set(base_path + ['network-settings', 'client-ipv6-pool', 'mask', v6_len])

        for ns in name_server:
            self.cli_set(base_path + ['network-settings', 'name-server', ns])
        for domain in split_dns:
            self.cli_set(base_path + ['network-settings', 'split-dns', domain])

        self.cli_set(base_path + ['ssl', 'ca-certificate', 'openconnect'])
        self.cli_set(base_path + ['ssl', 'certificate', 'openconnect'])

        self.cli_commit()

        # Verify configuration
        daemon_config = read_file(config_file)

        # authentication mode local password-otp
        self.assertIn(f'auth = "plain[passwd=/run/ocserv/ocpasswd,otp=/run/ocserv/users.oath]"', daemon_config)
        self.assertIn(f'ipv4-network = {v4_subnet}', daemon_config)
        self.assertIn(f'ipv6-network = {v6_prefix}', daemon_config)
        self.assertIn(f'ipv6-subnet-prefix = {v6_len}', daemon_config)

        for ns in name_server:
            self.assertIn(f'dns = {ns}', daemon_config)
        for domain in split_dns:
            self.assertIn(f'split-dns = {domain}', daemon_config)

        auth_config = read_file(auth_file)
        self.assertIn(f'{user}:*:$', auth_config)

        otp_config = read_file(otp_file)
        self.assertIn(f'HOTP/T30/6 {user} - {otp}', otp_config)

if __name__ == '__main__':
    unittest.main(verbosity=2)
