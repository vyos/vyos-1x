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

import re
import os
import unittest

from psutil import process_iter
from vyos.configsession import ConfigSession, ConfigSessionError
from vyos.util import read_file

OCSERV_CONF = '/run/ocserv/ocserv.conf'
base_path = ['vpn', 'openconnect']
cert = '/etc/ssl/certs/ssl-cert-snakeoil.pem'
cert_key = '/etc/ssl/private/ssl-cert-snakeoil.key'

class TestVpnOpenconnect(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())

    def tearDown(self):
        # Delete vpn openconnect configuration
        self.session.delete(base_path)
        self.session.commit()

        del self.session

    def test_vpn(self):
        user = 'vyos_user'
        password = 'vyos_pass'
        self.session.delete(base_path)
        self.session.set(base_path + ["authentication", "local-users", "username", user, "password", password])
        self.session.set(base_path + ["authentication", "mode", "local"])
        self.session.set(base_path + ["network-settings", "client-ip-settings", "subnet", "192.0.2.0/24"])
        self.session.set(base_path + ["ssl", "ca-cert-file", cert])
        self.session.set(base_path + ["ssl", "cert-file", cert])
        self.session.set(base_path + ["ssl", "key-file", cert_key])

        self.session.commit()

        # Check for running process
        self.assertTrue("ocserv-main" in (p.name() for p in process_iter()))

if __name__ == '__main__':
    unittest.main()
