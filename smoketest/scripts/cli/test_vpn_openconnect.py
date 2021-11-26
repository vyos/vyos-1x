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
from vyos.util import cmd
from os import path, mkdir

OCSERV_CONF = '/run/ocserv/ocserv.conf'
base_path   = ['vpn', 'openconnect']
cert_dir    = '/config/auth/'
ca_cert     = f'{cert_dir}ca.crt'
ssl_cert    = f'{cert_dir}server.crt'
ssl_key     = f'{cert_dir}server.key'

class TestVpnOpenconnect(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        # Delete vpn openconnect configuration
        self.cli_delete(base_path)
        self.cli_commit()

    def test_vpn(self):
        user = 'vyos_user'
        password = 'vyos_pass'
        self.cli_delete(base_path)
        self.cli_set(base_path + ["authentication", "local-users", "username", user, "password", password])
        self.cli_set(base_path + ["authentication", "mode", "local"])
        self.cli_set(base_path + ["network-settings", "client-ip-settings", "subnet", "192.0.2.0/24"])
        self.cli_set(base_path + ["ssl", "ca-cert-file", ca_cert])
        self.cli_set(base_path + ["ssl", "cert-file", ssl_cert])
        self.cli_set(base_path + ["ssl", "key-file", ssl_key])

        self.cli_commit()

        # Check for running process
        self.assertTrue(process_named_running('ocserv-main'))

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
