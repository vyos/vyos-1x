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

from ipaddress import IPv4Network
from netifaces import interfaces

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import cmd
from vyos.util import process_named_running
from vyos.util import read_file

PROCESS_NAME = 'openvpn'

base_path = ['interfaces', 'openvpn']
ca_cert  = '/config/auth/ovpn_test_ca.pem'
ssl_cert = '/config/auth/ovpn_test_server.pem'
ssl_key  = '/config/auth/ovpn_test_server.key'
dh_pem   = '/config/auth/ovpn_test_dh.pem'
s2s_key  = '/config/auth/ovpn_test_site2site.key'

remote_port = '1194'
protocol = 'udp'
path = []
interface = ''
remote_host = ''

class TestInterfacesOpenVPN(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        self.session.set(['interfaces', 'dummy', 'dum1328', 'address', '192.0.2.1/24'])

    def tearDown(self):
        self.session.delete(base_path)
        self.session.delete(['interfaces', 'dummy', 'dum1328'])
        self.session.commit()
        del self.session

    def test_client_interfaces(self):
        """ Create two OpenVPN client interfaces connecting to different
            server IP addresses. Validate configuration afterwards. """

        num_range = range(10, 12)
        for ii in num_range:
            interface = f'vtun{ii}'
            remote_host = f'192.0.2.{ii}'
            path = base_path + [interface]
            auth_hash = 'sha1'

            self.session.set(path + ['device-type', 'tun'])
            self.session.set(path + ['encryption', 'cipher', 'aes256'])
            self.session.set(path + ['hash', auth_hash])
            self.session.set(path + ['mode', 'client'])
            self.session.set(path + ['persistent-tunnel'])
            self.session.set(path + ['protocol', protocol])
            self.session.set(path + ['remote-host', remote_host])
            self.session.set(path + ['remote-port', remote_port])
            self.session.set(path + ['tls', 'ca-cert-file', ca_cert])
            self.session.set(path + ['tls', 'cert-file', ssl_cert])
            self.session.set(path + ['tls', 'key-file', ssl_key])

        self.session.commit()

        for ii in num_range:
            config_file = f'/run/openvpn/{interface}.conf'
            config = read_file(config_file)

            self.assertIn(f'dev {interface}', config)
            self.assertIn(f'dev-type tun', config)
            self.assertIn(f'persist-key', config)
            self.assertIn(f'proto {protocol}', config)
            self.assertIn(f'rport {remote_port}', config)
            self.assertIn(f'remote {remote_host}', config)
            self.assertIn(f'persist-tun', config)
            self.assertIn(f'auth {auth_hash}', config)
            self.assertIn(f'cipher aes-256-cbc', config)
            # TLS options
            self.assertIn(f'ca {ca_cert}', config)
            self.assertIn(f'cert {ssl_cert}', config)
            self.assertIn(f'key {ssl_key}', config)

            self.assertTrue(process_named_running(PROCESS_NAME))
            self.assertIn(interface, interfaces())

    def test_server_interfaces(self):
        """ Create two OpenVPN server interfaces using different client subnets.
            Validate configuration afterwards. """

        auth_hash = 'sha256'
        num_range = range(20, 22)
        port = ''
        for ii in num_range:
            interface = f'vtun{ii}'
            subnet = f'192.0.{ii}.0/24'
            path = base_path + [interface]
            port = str(2000 + ii)

            self.session.set(path + ['device-type', 'tun'])
            self.session.set(path + ['encryption', 'cipher', 'aes192'])
            self.session.set(path + ['hash', auth_hash])
            self.session.set(path + ['mode', 'server'])
            self.session.set(path + ['local-port', port])
            self.session.set(path + ['server', 'subnet', subnet])
            self.session.set(path + ['tls', 'ca-cert-file', ca_cert])
            self.session.set(path + ['tls', 'cert-file', ssl_cert])
            self.session.set(path + ['tls', 'key-file', ssl_key])
            self.session.set(path + ['tls', 'dh-file', dh_pem])

        self.session.commit()

        for ii in num_range:
            config_file = f'/run/openvpn/{interface}.conf'
            config = read_file(config_file)

            self.assertIn(f'dev {interface}', config)
            self.assertIn(f'dev-type tun', config)
            self.assertIn(f'persist-key', config)
            self.assertIn(f'proto udp', config) # default protocol
            self.assertIn(f'auth {auth_hash}', config)
            self.assertIn(f'cipher aes-192-cbc', config)
            self.assertIn(f'topology net30', config)
            self.assertIn(f'lport {port}', config)

            # TLS options
            self.assertIn(f'ca {ca_cert}', config)
            self.assertIn(f'cert {ssl_cert}', config)
            self.assertIn(f'key {ssl_key}', config)
            self.assertIn(f'dh {dh_pem}', config)

            # IP pool configuration
            netmask = IPv4Network(subnet).netmask
            network = IPv4Network(subnet).network_address
            self.assertIn(f'server {network} {netmask} nopool', config)

            self.assertTrue(process_named_running(PROCESS_NAME))
            self.assertIn(interface, interfaces())


    def test_site2site_interfaces(self):
        """
        """
        num_range = range(30, 32)
        port = ''
        local_address = ''
        remote_address = ''

        for ii in num_range:
            interface = f'vtun{ii}'
            local_address = f'192.0.{ii}.1'
            remote_address = f'172.16.{ii}.1'
            path = base_path + [interface]
            port = str(3000 + ii)

            self.session.set(path + ['mode', 'site-to-site'])
            self.session.set(path + ['local-port', port])
            self.session.set(path + ['local-address', local_address])
            self.session.set(path + ['remote-port', port])
            self.session.set(path + ['shared-secret-key-file', s2s_key])
            self.session.set(path + ['remote-address', remote_address])

        self.session.commit()

        for ii in num_range:
            config_file = f'/run/openvpn/{interface}.conf'
            config = read_file(config_file)

            self.assertIn(f'dev {interface}', config)
            self.assertIn(f'dev-type tun', config)
            self.assertIn(f'secret {s2s_key}', config)
            self.assertIn(f'lport {port}', config)
            self.assertIn(f'rport {port}', config)
            self.assertIn(f'ifconfig {local_address} {remote_address}', config)

            self.assertTrue(process_named_running(PROCESS_NAME))
            self.assertIn(interface, interfaces())


if __name__ == '__main__':
    # Our SSL certificates need a subject ...
    subject = '/C=DE/ST=BY/O=VyOS/localityName=Cloud/commonName=vyos/' \
              'organizationalUnitName=VyOS/emailAddress=maintainers@vyos.io/'

    if (not os.path.isfile(ssl_key) and not os.path.isfile(ssl_cert) and
        not os.path.isfile(ca_cert) and not os.path.isfile(dh_pem) and
        not os.path.isfile(s2s_key)):

        # Generate mandatory SSL certificate
        tmp = f'openssl req -newkey rsa:4096 -new -nodes -x509 -days 3650 '\
              f'-keyout {ssl_key} -out {ssl_cert} -subj {subject}'
        out = cmd(tmp)
        print(out)

        # Generate "CA"
        tmp = f'openssl req -new -x509 -key {ssl_key} -out {ca_cert} -subj {subject}'
        out = cmd(tmp)
        print(out)

        # Generate "DH" key
        tmp = f'openssl dhparam -out {dh_pem} 2048'
        out = cmd(tmp)
        print(out)

        # Generate site-2-site key
        tmp = f'openvpn --genkey --secret {s2s_key}'
        out = cmd(tmp)
        print(out)

        for file in [ca_cert, ssl_cert, ssl_key, dh_pem, s2s_key]:
            cmd(f'sudo chown openvpn:openvpn {file}')

    unittest.main()
