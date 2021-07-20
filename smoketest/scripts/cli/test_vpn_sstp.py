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

from base_accel_ppp_test import BasicAccelPPPTest
from vyos.util import cmd

pki_path = ['pki']
cert_data = 'MIICFDCCAbugAwIBAgIUfMbIsB/ozMXijYgUYG80T1ry+mcwCgYIKoZIzj0EAwIwWTELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzESMBAGA1UEAwwJVnlPUyBUZXN0MB4XDTIxMDcyMDEyNDUxMloXDTI2MDcxOTEyNDUxMlowWTELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzESMBAGA1UEAwwJVnlPUyBUZXN0MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE01HrLcNttqq4/PtoMua8rMWEkOdBu7vP94xzDO7A8C92ls1v86eePy4QllKCzIw3QxBIoCuH2peGRfWgPRdFsKNhMF8wDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMCAYYwHQYDVR0lBBYwFAYIKwYBBQUHAwIGCCsGAQUFBwMBMB0GA1UdDgQWBBSu+JnU5ZC4mkuEpqg2+Mk4K79oeDAKBggqhkjOPQQDAgNHADBEAiBEFdzQ/Bc3LftzngrY605UhA6UprHhAogKgROv7iR4QgIgEFUxTtW3xXJcnUPWhhUFhyZoqfn8dE93+dm/LDnp7C0='
key_data = 'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgPLpD0Ohhoq0g4nhx2KMIuze7ucKUt/lBEB2wc03IxXyhRANCAATTUestw222qrj8+2gy5rysxYSQ50G7u8/3jHMM7sDwL3aWzW/zp54/LhCWUoLMjDdDEEigK4fal4ZF9aA9F0Ww'

class TestVPNSSTPServer(BasicAccelPPPTest.TestCase):
    def setUp(self):
        self._base_path = ['vpn', 'sstp']
        self._process_name = 'accel-pppd'
        self._config_file = '/run/accel-pppd/sstp.conf'
        self._chap_secrets = '/run/accel-pppd/sstp.chap-secrets'
        super().setUp()

    def tearDown(self):
        self.cli_delete(pki_path)
        super().tearDown()

    def basic_config(self):
        self.cli_delete(pki_path)
        self.cli_set(pki_path + ['ca', 'sstp', 'certificate', cert_data])
        self.cli_set(pki_path + ['certificate', 'sstp', 'certificate', cert_data])
        self.cli_set(pki_path + ['certificate', 'sstp', 'private', 'key', key_data])
        # SSL is mandatory
        self.set(['ssl', 'ca-certificate', 'sstp'])
        self.set(['ssl', 'certificate', 'sstp'])
        self.set(['client-ip-pool', 'subnet', '192.0.2.0/24'])

        super().basic_config()

if __name__ == '__main__':
    unittest.main(verbosity=2)
