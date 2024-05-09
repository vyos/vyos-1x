#!/usr/bin/env python3
#
# Copyright (C) 2020-2023 VyOS maintainers and contributors
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
from vyos.utils.file import read_file

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
+dm/LDnp7C0="""

key_data = """
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgPLpD0Ohhoq0g4nhx
2KMIuze7ucKUt/lBEB2wc03IxXyhRANCAATTUestw222qrj8+2gy5rysxYSQ50G7
u8/3jHMM7sDwL3aWzW/zp54/LhCWUoLMjDdDEEigK4fal4ZF9aA9F0Ww
"""

class TestVPNSSTPServer(BasicAccelPPPTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['vpn', 'sstp']
        cls._config_file = '/run/accel-pppd/sstp.conf'
        cls._chap_secrets = '/run/accel-pppd/sstp.chap-secrets'
        cls._protocol_section = 'sstp'
        # call base-classes classmethod
        super(TestVPNSSTPServer, cls).setUpClass()

        cls.cli_set(cls, pki_path + ['ca', 'sstp', 'certificate', cert_data.replace('\n','')])
        cls.cli_set(cls, pki_path + ['certificate', 'sstp', 'certificate', cert_data.replace('\n','')])
        cls.cli_set(cls, pki_path + ['certificate', 'sstp', 'private', 'key', key_data.replace('\n','')])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, pki_path)
        super(TestVPNSSTPServer, cls).tearDownClass()

    def basic_protocol_specific_config(self):
        self.set(['ssl', 'ca-certificate', 'sstp'])
        self.set(['ssl', 'certificate', 'sstp'])

    def test_accel_local_authentication(self):
        # Change default port
        port = '8443'
        self.set(['port', port])

        self.basic_config()
        super().test_accel_local_authentication()

        config = read_file(self._config_file)
        self.assertIn(f'port={port}', config)

    def test_sstp_host_name(self):
        host_name = 'test.vyos.io'
        self.set(['host-name', host_name])

        self.basic_config()
        self.cli_commit()

        config = read_file(self._config_file)
        self.assertIn(f'host-name={host_name}', config)


if __name__ == '__main__':
    unittest.main(verbosity=2)
