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

process_name = 'accel-pppd'
ca_cert = '/tmp/ca.crt'
ssl_cert = '/tmp/server.crt'
ssl_key = '/tmp/server.key'

class TestVPNSSTPServer(BasicAccelPPPTest.BaseTest):
    def setUp(self):
        self._base_path = ['vpn', 'sstp']
        self._process_name = 'accel-pppd'
        self._config_file = '/run/accel-pppd/sstp.conf'
        self._chap_secrets = '/run/accel-pppd/sstp.chap-secrets'

        super().setUp()

    def tearDown(self):
        super().tearDown()

    def basic_config(self):
        # SSL is mandatory
        self.set(['ssl', 'ca-cert-file', ca_cert])
        self.set(['ssl', 'cert-file', ssl_cert])
        self.set(['ssl', 'key-file', ssl_key])

        self.set(['client-ip-pool', 'subnet', '192.0.2.0/24'])
        self.set(['gateway-address', '1.1.1.1'])

        super().basic_config()

if __name__ == '__main__':
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

    unittest.main()
