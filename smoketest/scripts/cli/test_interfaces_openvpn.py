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

import os
import unittest

from netifaces import interfaces

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import cmd
from vyos.util import process_named_running
from vyos.util import read_file

PROCESS_NAME = 'openvpn'

base_path = ['interfaces', 'openvpn']
ca_cert  = '/config/auth/ovpn_test_ca.crt'
ssl_cert = '/config/auth/ovpn_test_server.crt'
ssl_key  = '/config/auth/ovpn_test_server.key'

class TestInterfacesOpenVPN(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())

    def tearDown(self):
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_client(self):
        """ Basic OpenVPN client test """
        interface = 'vtun10'
        remote_host = '192.0.2.1'
        remote_port = '1194'
        protocol = 'udp'
        path = base_path + [interface]

        self.session.set(path + ['device-type', 'tun'])
        self.session.set(path + ['encryption', 'cipher', 'aes256'])
        self.session.set(path + ['hash', 'sha1'])
        self.session.set(path + ['mode', 'client'])
        self.session.set(path + ['persistent-tunnel'])
        self.session.set(path + ['protocol', protocol])
        self.session.set(path + ['remote-host', remote_host])
        self.session.set(path + ['remote-port', remote_port])
        self.session.set(path + ['tls', 'ca-cert-file', ca_cert])
        self.session.set(path + ['tls', 'cert-file', ssl_cert])
        self.session.set(path + ['tls', 'key-file', ssl_key])

        self.session.commit()

        config_file = f'/run/openvpn/{interface}.conf'
        config = read_file(config_file)

        self.assertIn(f'dev {interface}', config)
        self.assertIn('dev-type tun', config)
        self.assertIn('persist-key', config)
        self.assertIn(f'proto {protocol}', config)
        self.assertIn(f'rport {remote_port}', config)
        self.assertIn(f'remote {remote_host}', config)
        self.assertIn('persist-tun', config)

        self.assertTrue(process_named_running(PROCESS_NAME))
        self.assertIn(interface, interfaces())

if __name__ == '__main__':
    # Our SSL certificates need a subject ...
    subject = '/C=DE/ST=BY/O=VyOS/localityName=Cloud/commonName=vyos/' \
              'organizationalUnitName=VyOS/emailAddress=maintainers@vyos.io/'

    if not os.path.isfile(ssl_key) and not os.path.isfile(ssl_cert) and not os.path.isfile(ca_cert):
        # Generate mandatory SSL certificate
        tmp = f'openssl req -newkey rsa:4096 -new -nodes -x509 -days 3650 '\
              f'-keyout {ssl_key} -out {ssl_cert} -subj {subject}'
        cmd(tmp)

        # Generate "CA"
        tmp = f'openssl req -new -x509 -key {ssl_key} -out {ca_cert} '\
              f'-subj {subject}'
        cmd(tmp)

        for file in [ca_cert, ssl_cert, ssl_key]:
            cmd(f'sudo chown openvpn:openvpn {file}')

    unittest.main()
