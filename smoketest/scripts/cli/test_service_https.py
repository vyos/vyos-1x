#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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
from vyos.util import run

base_path = ['service', 'https']

pki_base = ['pki']
cert_data = 'MIICFDCCAbugAwIBAgIUfMbIsB/ozMXijYgUYG80T1ry+mcwCgYIKoZIzj0EAwIwWTELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzESMBAGA1UEAwwJVnlPUyBUZXN0MB4XDTIxMDcyMDEyNDUxMloXDTI2MDcxOTEyNDUxMlowWTELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzESMBAGA1UEAwwJVnlPUyBUZXN0MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE01HrLcNttqq4/PtoMua8rMWEkOdBu7vP94xzDO7A8C92ls1v86eePy4QllKCzIw3QxBIoCuH2peGRfWgPRdFsKNhMF8wDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMCAYYwHQYDVR0lBBYwFAYIKwYBBQUHAwIGCCsGAQUFBwMBMB0GA1UdDgQWBBSu+JnU5ZC4mkuEpqg2+Mk4K79oeDAKBggqhkjOPQQDAgNHADBEAiBEFdzQ/Bc3LftzngrY605UhA6UprHhAogKgROv7iR4QgIgEFUxTtW3xXJcnUPWhhUFhyZoqfn8dE93+dm/LDnp7C0='
key_data = 'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgPLpD0Ohhoq0g4nhx2KMIuze7ucKUt/lBEB2wc03IxXyhRANCAATTUestw222qrj8+2gy5rysxYSQ50G7u8/3jHMM7sDwL3aWzW/zp54/LhCWUoLMjDdDEEigK4fal4ZF9aA9F0Ww'

class TestHTTPSService(VyOSUnitTestSHIM.TestCase):
    def setUp(self):
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        self.cli_delete(base_path)
        self.cli_delete(pki_base)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_delete(pki_base)
        self.cli_commit()

    def test_default(self):
        self.cli_set(base_path)
        self.cli_commit()

        ret = run('sudo /usr/sbin/nginx -t')
        self.assertEqual(ret, 0)

    def test_server_block(self):
        vhost_id = 'example'
        address = '0.0.0.0'
        port = '8443'
        name = 'example.org'

        test_path = base_path + ['virtual-host', vhost_id]

        self.cli_set(test_path + ['listen-address', address])
        self.cli_set(test_path + ['listen-port', port])
        self.cli_set(test_path + ['server-name', name])

        self.cli_commit()

        ret = run('sudo /usr/sbin/nginx -t')
        self.assertEqual(ret, 0)

    def test_certificate(self):
        self.cli_set(pki_base + ['certificate', 'test_https', 'certificate', cert_data])
        self.cli_set(pki_base + ['certificate', 'test_https', 'private', 'key', key_data])

        self.cli_set(base_path + ['certificates', 'certificate', 'test_https'])

        self.cli_commit()

        ret = run('sudo /usr/sbin/nginx -t')
        self.assertEqual(ret, 0)

if __name__ == '__main__':
    unittest.main(verbosity=2)
