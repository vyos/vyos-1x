#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

OCSERV_CONF = '/run/ocserv/ocserv.conf'
base_path = ['vpn', 'openconnect']

pki_path = ['pki']
cert_data = 'MIICFDCCAbugAwIBAgIUfMbIsB/ozMXijYgUYG80T1ry+mcwCgYIKoZIzj0EAwIwWTELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzESMBAGA1UEAwwJVnlPUyBUZXN0MB4XDTIxMDcyMDEyNDUxMloXDTI2MDcxOTEyNDUxMlowWTELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzESMBAGA1UEAwwJVnlPUyBUZXN0MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE01HrLcNttqq4/PtoMua8rMWEkOdBu7vP94xzDO7A8C92ls1v86eePy4QllKCzIw3QxBIoCuH2peGRfWgPRdFsKNhMF8wDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMCAYYwHQYDVR0lBBYwFAYIKwYBBQUHAwIGCCsGAQUFBwMBMB0GA1UdDgQWBBSu+JnU5ZC4mkuEpqg2+Mk4K79oeDAKBggqhkjOPQQDAgNHADBEAiBEFdzQ/Bc3LftzngrY605UhA6UprHhAogKgROv7iR4QgIgEFUxTtW3xXJcnUPWhhUFhyZoqfn8dE93+dm/LDnp7C0='
key_data = 'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgPLpD0Ohhoq0g4nhx2KMIuze7ucKUt/lBEB2wc03IxXyhRANCAATTUestw222qrj8+2gy5rysxYSQ50G7u8/3jHMM7sDwL3aWzW/zp54/LhCWUoLMjDdDEEigK4fal4ZF9aA9F0Ww'

class TestVpnOpenconnect(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        # Delete vpn openconnect configuration
        self.cli_delete(pki_path)
        self.cli_delete(base_path)
        self.cli_commit()

    def test_vpn(self):
        user = 'vyos_user'
        password = 'vyos_pass'
        otp = '37500000026900000000200000000000'

        self.cli_delete(pki_path)
        self.cli_delete(base_path)

        self.cli_set(pki_path + ['ca', 'openconnect', 'certificate', cert_data])
        self.cli_set(pki_path + ['certificate', 'openconnect', 'certificate', cert_data])
        self.cli_set(pki_path + ['certificate', 'openconnect', 'private', 'key', key_data])

        self.cli_set(base_path + ["authentication", "local-users", "username", user, "password", password])
        self.cli_set(base_path + ["authentication", "local-users", "username", user, "otp", "key", otp])
        self.cli_set(base_path + ["authentication", "mode", "local", "password-otp"])
        self.cli_set(base_path + ["network-settings", "client-ip-settings", "subnet", "192.0.2.0/24"])
        self.cli_set(base_path + ["ssl", "ca-certificate", 'openconnect'])
        self.cli_set(base_path + ["ssl", "certificate", 'openconnect'])

        self.cli_commit()

        # Check for running process
        self.assertTrue(process_named_running('ocserv-main'))

if __name__ == '__main__':
    unittest.main(verbosity=2)
