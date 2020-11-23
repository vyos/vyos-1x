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

from glob import glob
from ipaddress import IPv4Network
from netifaces import interfaces

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import cmd
from vyos.util import process_named_running
from vyos.util import read_file
from vyos.template import address_from_cidr
from vyos.template import dec_ip
from vyos.template import inc_ip
from vyos.template import last_host_address
from vyos.template import netmask_from_cidr

PROCESS_NAME = 'openvpn'

base_path = ['interfaces', 'openvpn']
ca_cert  = '/config/auth/ovpn_test_ca.pem'
ssl_cert = '/config/auth/ovpn_test_server.pem'
ssl_key  = '/config/auth/ovpn_test_server.key'
dh_pem   = '/config/auth/ovpn_test_dh.pem'
s2s_key  = '/config/auth/ovpn_test_site2site.key'
auth_key = '/config/auth/ovpn_test_tls_auth.key'

remote_port = '1194'
protocol = 'udp'
path = []
interface = ''
remote_host = ''
vrf_name = 'orange'
dummy_if = 'dum1301'

def get_vrf(interface):
    for upper in glob(f'/sys/class/net/{interface}/upper*'):
        # an upper interface could be named: upper_bond0.1000.1100, thus
        # we need top drop the upper_ prefix
        tmp = os.path.basename(upper)
        tmp = tmp.replace('upper_', '')
        return tmp

class TestInterfacesOpenVPN(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        self.session.set(['interfaces', 'dummy', dummy_if, 'address', '192.0.2.1/32'])
        self.session.set(['vrf', 'name', vrf_name, 'table', '12345'])

    def tearDown(self):
        self.session.delete(base_path)
        self.session.delete(['interfaces', 'dummy', dummy_if])
        self.session.delete(['vrf'])
        self.session.commit()
        del self.session

    def test_client_verify(self):
        """
        Create OpenVPN client interface and test verify() steps.
        """
        interface = 'vtun2000'
        path = base_path + [interface]
        self.session.set(path + ['mode', 'client'])

        # check validate() - cannot specify both "encryption disable-ncp" and
        # "encryption ncp-ciphers" at the same time
        self.session.set(path + ['encryption', 'disable-ncp'])
        self.session.set(path + ['encryption', 'ncp-ciphers', 'aes192gcm'])

        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['encryption', 'ncp-ciphers'])

        # check validate() - cannot specify local-port in client mode
        self.session.set(path + ['local-port', '5000'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['local-port'])

        # check validate() - cannot specify local-host in client mode
        self.session.set(path + ['local-host', '127.0.0.1'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['local-host'])

        # check validate() - cannot specify protocol tcp-passive in client mode
        self.session.set(path + ['protocol', 'tcp-passive'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['protocol'])

        # check validate() - remote-host must be set in client mode
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(path + ['remote-host', '192.0.9.9'])

        # check validate() - cannot specify "tls dh-file" in client mode
        self.session.set(path + ['tls', 'dh-file', dh_pem])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['tls'])

        # check validate() - must specify one of "shared-secret-key-file" and "tls"
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(path + ['shared-secret-key-file', s2s_key])

        # check validate() - must specify one of "shared-secret-key-file" and "tls"
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['shared-secret-key-file', s2s_key])

        self.session.set(path + ['tls', 'ca-cert-file', ca_cert])
        self.session.set(path + ['tls', 'cert-file', ssl_cert])
        self.session.set(path + ['tls', 'key-file', ssl_key])

        # check validate() - can not have auth username without a password
        self.session.set(path + ['authentication', 'username', 'vyos'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(path + ['authentication', 'password', 'vyos'])

        # client commit must pass
        self.session.commit()

        self.assertTrue(process_named_running(PROCESS_NAME))
        self.assertIn(interface, interfaces())


    def test_client_interfaces(self):
        """
        Create OpenVPN client interfaces connecting to different
        server IP addresses. Validate configuration afterwards.
        """
        num_range = range(10, 15)
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
            self.session.set(path + ['vrf', vrf_name])
            self.session.set(path + ['authentication', 'username', interface+'user'])
            self.session.set(path + ['authentication', 'password', interface+'secretpw'])

        self.session.commit()

        for ii in num_range:
            interface = f'vtun{ii}'
            remote_host = f'192.0.2.{ii}'
            config_file = f'/run/openvpn/{interface}.conf'
            pw_file = f'/run/openvpn/{interface}.pw'
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
            self.assertEqual(get_vrf(interface), vrf_name)
            self.assertIn(interface, interfaces())

            pw = cmd(f'sudo cat {pw_file}')
            self.assertIn(f'{interface}user', pw)
            self.assertIn(f'{interface}secretpw', pw)

        # check that no interface remained after deleting them
        self.session.delete(base_path)
        self.session.commit()

        for ii in num_range:
            interface = f'vtun{ii}'
            self.assertNotIn(interface, interfaces())

    def test_server_verify(self):
        """
        Create one OpenVPN server interface and check required verify() stages
        """
        interface = 'vtun5000'
        path = base_path + [interface]

        # check validate() - must speciy operating mode
        self.session.set(path)
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(path + ['mode', 'server'])

        # check validate() - cannot specify protocol tcp-active in server mode
        self.session.set(path + ['protocol', 'tcp-active'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['protocol'])

        # check validate() - cannot specify local-port in client mode
        self.session.set(path + ['remote-port', '5000'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['remote-port'])

        # check validate() - cannot specify local-host in client mode
        self.session.set(path + ['remote-host', '127.0.0.1'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['remote-host'])

        # check validate() - must specify "tls dh-file" when not using EC keys
        # in server mode
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(path + ['tls', 'dh-file', dh_pem])

        # check validate() - must specify "server subnet" or add interface to
        # bridge in server mode
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

        # check validate() - server client-ip-pool is too large
        # [100.64.0.4 -> 100.127.255.251 = 4194295], maximum is 65536 addresses.
        self.session.set(path + ['server', 'subnet', '100.64.0.0/10'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

        # check validate() - cannot specify more than 1 IPv4 and 1 IPv6 server subnet
        self.session.set(path + ['server', 'subnet', '100.64.0.0/20'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['server', 'subnet', '100.64.0.0/10'])

        # check validate() - must specify "tls ca-cert-file"
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(path + ['tls', 'ca-cert-file', ca_cert])

        # check validate() - must specify "tls cert-file"
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(path + ['tls', 'cert-file', ssl_cert])

        # check validate() - must specify "tls key-file"
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(path + ['tls', 'key-file', ssl_key])

        # check validate() - cannot specify "tls role" in client-server mode'
        self.session.set(path + ['tls', 'role', 'active'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

        # check validate() - cannot specify "tls role" in client-server mode'
        self.session.set(path + ['tls', 'auth-file', auth_key])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

        # check validate() - cannot specify "tcp-passive" when "tls role" is "active"
        self.session.set(path + ['protocol', 'tcp-passive'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['protocol'])

        # check validate() - cannot specify "tls dh-file" when "tls role" is "active"
        self.session.set(path + ['tls', 'dh-file', dh_pem])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['tls', 'dh-file'])

        # Now test the other path with tls role passive
        self.session.set(path + ['tls', 'role', 'passive'])
        # check validate() - cannot specify "tcp-active" when "tls role" is "passive"
        self.session.set(path + ['protocol', 'tcp-active'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['protocol'])


        # check validate() - must specify "tls dh-file" when "tls role" is "passive"
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(path + ['tls', 'dh-file', dh_pem])

        self.session.commit()

        self.assertTrue(process_named_running(PROCESS_NAME))
        self.assertIn(interface, interfaces())

    def test_server_subnet_topology(self):
        """
        Create OpenVPN server interfaces using different client subnets.
        Validate configuration afterwards.
        """
        auth_hash = 'sha256'
        num_range = range(20, 25)
        port = ''
        client1_routes = ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']
        for ii in num_range:
            interface = f'vtun{ii}'
            subnet = f'192.0.{ii}.0/24'
            client_ip = inc_ip(subnet, '5')
            path = base_path + [interface]
            port = str(2000 + ii)

            self.session.set(path + ['device-type', 'tun'])
            self.session.set(path + ['encryption', 'cipher', 'aes192'])
            self.session.set(path + ['hash', auth_hash])
            self.session.set(path + ['mode', 'server'])
            self.session.set(path + ['local-port', port])
            self.session.set(path + ['server', 'subnet', subnet])
            self.session.set(path + ['server', 'topology', 'subnet'])
            self.session.set(path + ['keep-alive', 'failure-count', '5'])
            self.session.set(path + ['keep-alive', 'interval', '5'])

            # clients
            self.session.set(path + ['server', 'client', 'client1', 'ip', client_ip])
            for route in client1_routes:
                self.session.set(path + ['server', 'client', 'client1', 'subnet', route])

            self.session.set(path + ['replace-default-route'])
            self.session.set(path + ['tls', 'ca-cert-file', ca_cert])
            self.session.set(path + ['tls', 'cert-file', ssl_cert])
            self.session.set(path + ['tls', 'key-file', ssl_key])
            self.session.set(path + ['tls', 'dh-file', dh_pem])
            self.session.set(path + ['vrf', vrf_name])

        self.session.commit()

        for ii in num_range:
            interface = f'vtun{ii}'
            subnet = f'192.0.{ii}.0/24'

            start_addr = inc_ip(subnet, '2')
            stop_addr = last_host_address(subnet)

            client_ip = inc_ip(subnet, '5')
            client_netmask = netmask_from_cidr(subnet)

            port = str(2000 + ii)

            config_file = f'/run/openvpn/{interface}.conf'
            client_config_file = f'/run/openvpn/ccd/{interface}/client1'
            config = read_file(config_file)

            self.assertIn(f'dev {interface}', config)
            self.assertIn(f'dev-type tun', config)
            self.assertIn(f'persist-key', config)
            self.assertIn(f'proto udp', config) # default protocol
            self.assertIn(f'auth {auth_hash}', config)
            self.assertIn(f'cipher aes-192-cbc', config)
            self.assertIn(f'topology subnet', config)
            self.assertIn(f'lport {port}', config)
            self.assertIn(f'push "redirect-gateway def1"', config)
            self.assertIn(f'keepalive 5 25', config)

            # TLS options
            self.assertIn(f'ca {ca_cert}', config)
            self.assertIn(f'cert {ssl_cert}', config)
            self.assertIn(f'key {ssl_key}', config)
            self.assertIn(f'dh {dh_pem}', config)

            # IP pool configuration
            netmask = IPv4Network(subnet).netmask
            network = IPv4Network(subnet).network_address
            self.assertIn(f'server {network} {netmask} nopool', config)

            # Verify client
            client_config = read_file(client_config_file)

            self.assertIn(f'ifconfig-push {client_ip} {client_netmask}', client_config)
            for route in client1_routes:
                self.assertIn('iroute {} {}'.format(address_from_cidr(route), netmask_from_cidr(route)), client_config)

            self.assertTrue(process_named_running(PROCESS_NAME))
            self.assertEqual(get_vrf(interface), vrf_name)
            self.assertIn(interface, interfaces())

        # check that no interface remained after deleting them
        self.session.delete(base_path)
        self.session.commit()

        for ii in num_range:
            interface = f'vtun{ii}'
            self.assertNotIn(interface, interfaces())

    def test_server_net30_topology(self):
        """
        Create OpenVPN server interfaces (net30) using different client
        subnets. Validate configuration afterwards.
        """
        auth_hash = 'sha256'
        num_range = range(20, 25)
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
            self.session.set(path + ['server', 'topology', 'net30'])
            self.session.set(path + ['replace-default-route'])
            self.session.set(path + ['keep-alive', 'failure-count', '10'])
            self.session.set(path + ['keep-alive', 'interval', '5'])
            self.session.set(path + ['tls', 'ca-cert-file', ca_cert])
            self.session.set(path + ['tls', 'cert-file', ssl_cert])
            self.session.set(path + ['tls', 'key-file', ssl_key])
            self.session.set(path + ['tls', 'dh-file', dh_pem])
            self.session.set(path + ['vrf', vrf_name])

        self.session.commit()

        for ii in num_range:
            interface = f'vtun{ii}'
            subnet = f'192.0.{ii}.0/24'
            start_addr = inc_ip(subnet, '4')
            stop_addr = dec_ip(last_host_address(subnet), '1')
            port = str(2000 + ii)

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
            self.assertIn(f'push "redirect-gateway def1"', config)
            self.assertIn(f'keepalive 5 50', config)

            # TLS options
            self.assertIn(f'ca {ca_cert}', config)
            self.assertIn(f'cert {ssl_cert}', config)
            self.assertIn(f'key {ssl_key}', config)
            self.assertIn(f'dh {dh_pem}', config)

            # IP pool configuration
            netmask = IPv4Network(subnet).netmask
            network = IPv4Network(subnet).network_address
            self.assertIn(f'server {network} {netmask} nopool', config)
            self.assertIn(f'ifconfig-pool {start_addr} {stop_addr}', config)

            self.assertTrue(process_named_running(PROCESS_NAME))
            self.assertEqual(get_vrf(interface), vrf_name)
            self.assertIn(interface, interfaces())

        # check that no interface remained after deleting them
        self.session.delete(base_path)
        self.session.commit()

        for ii in num_range:
            interface = f'vtun{ii}'
            self.assertNotIn(interface, interfaces())

    def test_site2site_verify(self):
        """
        Create one OpenVPN site2site interface and check required verify() stages
        """
        interface = 'vtun5000'
        path = base_path + [interface]

        self.session.set(path + ['mode', 'site-to-site'])

        # check validate() - encryption ncp-ciphers cannot be specified in site-to-site mode
        self.session.set(path + ['encryption', 'ncp-ciphers', 'aes192gcm'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['encryption'])

        # check validate() - must specify "local-address" or add interface to bridge
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(path + ['local-address', '10.0.0.1'])
        self.session.set(path + ['local-address', '2001:db8:1::1'])

        # check validate() - cannot specify more than 1 IPv4 local-address
        self.session.set(path + ['local-address', '10.0.0.2'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['local-address', '10.0.0.2'])

        # check validate() - cannot specify more than 1 IPv6 local-address
        self.session.set(path + ['local-address', '2001:db8:1::2'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['local-address', '2001:db8:1::2'])

        # check validate() - IPv4 "local-address" requires IPv4 "remote-address"
        # or IPv4 "local-address subnet"
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(path + ['remote-address', '192.168.0.1'])
        self.session.set(path + ['remote-address', '2001:db8:ffff::1'])

        # check validate() - Cannot specify more than 1 IPv4 "remote-address"
        self.session.set(path + ['remote-address', '192.168.0.2'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['remote-address', '192.168.0.2'])

        # check validate() - Cannot specify more than 1 IPv6 "remote-address"
        self.session.set(path + ['remote-address', '2001:db8:ffff::2'])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(path + ['remote-address', '2001:db8:ffff::2'])

        # check validate() - Must specify one of "shared-secret-key-file" and "tls"
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(path + ['shared-secret-key-file', s2s_key])

        self.session.commit()

    def test_site2site_interfaces_tun(self):
        """
        Create two OpenVPN site-to-site interfaces
        """
        num_range = range(30, 35)
        port = ''
        local_address = ''
        remote_address = ''

        for ii in num_range:
            interface = f'vtun{ii}'
            local_address = f'192.0.{ii}.1'
            local_address_subnet = '255.255.255.252'
            remote_address = f'172.16.{ii}.1'
            path = base_path + [interface]
            port = str(3000 + ii)

            self.session.set(path + ['local-address', local_address])

            # even numbers use tun type, odd numbers use tap type
            if ii % 2 == 0:
                self.session.set(path + ['device-type', 'tun'])
            else:
                self.session.set(path + ['device-type', 'tap'])
                self.session.set(path + ['local-address', local_address, 'subnet-mask', local_address_subnet])

            self.session.set(path + ['mode', 'site-to-site'])
            self.session.set(path + ['local-port', port])
            self.session.set(path + ['remote-port', port])
            self.session.set(path + ['shared-secret-key-file', s2s_key])
            self.session.set(path + ['remote-address', remote_address])
            self.session.set(path + ['vrf', vrf_name])

        self.session.commit()

        for ii in num_range:
            interface = f'vtun{ii}'
            local_address = f'192.0.{ii}.1'
            remote_address = f'172.16.{ii}.1'
            port = str(3000 + ii)

            config_file = f'/run/openvpn/{interface}.conf'
            config = read_file(config_file)

            # even numbers use tun type, odd numbers use tap type
            if ii % 2 == 0:
                self.assertIn(f'dev-type tun', config)
                self.assertIn(f'ifconfig {local_address} {remote_address}', config)
            else:
                self.assertIn(f'dev-type tap', config)
                self.assertIn(f'ifconfig {local_address} {local_address_subnet}', config)

            self.assertIn(f'dev {interface}', config)
            self.assertIn(f'secret {s2s_key}', config)
            self.assertIn(f'lport {port}', config)
            self.assertIn(f'rport {port}', config)


            self.assertTrue(process_named_running(PROCESS_NAME))
            self.assertEqual(get_vrf(interface), vrf_name)
            self.assertIn(interface, interfaces())


        # check that no interface remained after deleting them
        self.session.delete(base_path)
        self.session.commit()

        for ii in num_range:
            interface = f'vtun{ii}'
            self.assertNotIn(interface, interfaces())


if __name__ == '__main__':
    # Our SSL certificates need a subject ...
    subject = '/C=DE/ST=BY/O=VyOS/localityName=Cloud/commonName=vyos/' \
              'organizationalUnitName=VyOS/emailAddress=maintainers@vyos.io/'

    if not (os.path.isfile(ssl_key) and os.path.isfile(ssl_cert)):
        # Generate mandatory SSL certificate
        tmp = f'openssl req -newkey rsa:4096 -new -nodes -x509 -days 3650 '\
              f'-keyout {ssl_key} -out {ssl_cert} -subj {subject}'
        print(cmd(tmp))

    if not os.path.isfile(ca_cert):
        # Generate "CA"
        tmp = f'openssl req -new -x509 -key {ssl_key} -out {ca_cert} -subj {subject}'
        print(cmd(tmp))

    if not os.path.isfile(dh_pem):
        # Generate "DH" key
        tmp = f'openssl dhparam -out {dh_pem} 2048'
        print(cmd(tmp))

    if not os.path.isfile(s2s_key):
        # Generate site-2-site key
        tmp = f'openvpn --genkey --secret {s2s_key}'
        print(cmd(tmp))

    if not os.path.isfile(auth_key):
        # Generate TLS auth key
        tmp = f'openvpn --genkey --secret {auth_key}'
        print(cmd(tmp))

    for file in [ca_cert, ssl_cert, ssl_key, dh_pem, s2s_key, auth_key]:
        cmd(f'sudo chown openvpn:openvpn {file}')

    unittest.main()
