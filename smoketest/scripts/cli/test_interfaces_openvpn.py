#!/usr/bin/env python3
#
# Copyright (C) 2020-2024 VyOS maintainers and contributors
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

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.process import cmd
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file
from vyos.template import address_from_cidr
from vyos.template import inc_ip
from vyos.template import last_host_address
from vyos.template import netmask_from_cidr

PROCESS_NAME = 'openvpn'

base_path = ['interfaces', 'openvpn']

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
+dm/LDnp7C0=
"""

key_data = """
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgPLpD0Ohhoq0g4nhx
2KMIuze7ucKUt/lBEB2wc03IxXyhRANCAATTUestw222qrj8+2gy5rysxYSQ50G7
u8/3jHMM7sDwL3aWzW/zp54/LhCWUoLMjDdDEEigK4fal4ZF9aA9F0Ww
"""

dh_data = """
MIIBCAKCAQEApzGAPcQlLJiOyfGZgl1qxNgufXkdpjG7lMaOrO4TGr1giFe3jIFO
FxJNC/G9Dn+KSukaWssVVR+Jwr/JesZFPawihS03wC7cZsccykNRIjiteqJDwYJZ
UHieOxyCuCeY4pqOUCl1uswRGjLvIFtwynpnXKKuz2YtjNifma90PEgv/vVWKix+
Q0TAbdbzJzO5xp8UVn9DuYfSr10k3LbDqDM7w5ezHZxFk24S5pN/yoOpdbxB8TS6
7q3IYXxR3F+RseKu4J3AvkxXSP1j7COXddPpLnvbJT/SW8NrjuC/n0eKGvmeyqNv
108Y89jnT79MxMMRQk66iwlsd1m4pa/OYwIBAg==
"""

ovpn_key_data = """
443f2a710ac411c36894b2531e62c4550b079b8f3f08997f4be57c64abfdaaa4
31d2396b01ecec3a2c0618959e8186d99f489742d25673ffb3268841ebb2e704
2a2daabe584e79d51d2b1d7409bf8840f7e42efa3e660a521719b04ee88b9043
e6315ae12da7c9abd55f67eeed71a9ee8c6e163b5d2661fc332cf90cb45658b4
adf892f79537d37d3a3d90da283ce885adf325ffd2b5be92067cdf0345c7712c
9d36b642c170351b6d9ce9f6230c7a2617b0c181121bce7d5373404fb68e6521
0b36e6d40ef2769cf8990503859f6f2db3c85ba74420430a6250d6a74ca51ece
4b85124bfdfec0c8a530cefa7350378d81a4539f74bed832a902ae4798142e4a
"""

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

class TestInterfacesOpenVPN(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestInterfacesOpenVPN, cls).setUpClass()

        cls.cli_set(cls, ['interfaces', 'dummy', dummy_if, 'address', '192.0.2.1/32'])
        cls.cli_set(cls, ['vrf', 'name', vrf_name, 'table', '12345'])

        cls.cli_set(cls, ['pki', 'ca', 'ovpn_test', 'certificate', cert_data.replace('\n','')])
        cls.cli_set(cls, ['pki', 'certificate', 'ovpn_test', 'certificate', cert_data.replace('\n','')])
        cls.cli_set(cls, ['pki', 'certificate', 'ovpn_test', 'private', 'key', key_data.replace('\n','')])
        cls.cli_set(cls, ['pki', 'dh', 'ovpn_test', 'parameters', dh_data.replace('\n','')])
        cls.cli_set(cls, ['pki', 'openvpn', 'shared-secret', 'ovpn_test', 'key', ovpn_key_data.replace('\n','')])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['interfaces', 'dummy', dummy_if])
        cls.cli_delete(cls, ['vrf'])

        super(TestInterfacesOpenVPN, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_openvpn_client_verify(self):
        # Create OpenVPN client interface and test verify() steps.
        interface = 'vtun2000'
        path = base_path + [interface]
        self.cli_set(path + ['mode', 'client'])
        self.cli_set(path + ['encryption', 'data-ciphers', 'aes192gcm'])

        # check validate() - cannot specify local-port in client mode
        self.cli_set(path + ['local-port', '5000'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['local-port'])

        # check validate() - cannot specify local-host in client mode
        self.cli_set(path + ['local-host', '127.0.0.1'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['local-host'])

        # check validate() - cannot specify protocol tcp-passive in client mode
        self.cli_set(path + ['protocol', 'tcp-passive'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['protocol'])

        # check validate() - remote-host must be set in client mode
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(path + ['remote-host', '192.0.9.9'])

        # check validate() - cannot specify "tls dh-params" in client mode
        self.cli_set(path + ['tls', 'dh-params', 'ovpn_test'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['tls'])

        # check validate() - must specify one of "shared-secret-key" and "tls"
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(path + ['shared-secret-key', 'ovpn_test'])

        # check validate() - must specify one of "shared-secret-key" and "tls"
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['shared-secret-key', 'ovpn_test'])

        # check validate() - cannot specify "encryption cipher" in  client mode
        self.cli_set(path + ['encryption', 'cipher', 'aes192gcm'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['encryption', 'cipher'])

        self.cli_set(path + ['tls', 'ca-certificate', 'ovpn_test'])
        self.cli_set(path + ['tls', 'certificate', 'ovpn_test'])

        # check validate() - can not have auth username without a password
        self.cli_set(path + ['authentication', 'username', 'vyos'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(path + ['authentication', 'password', 'vyos'])

        # client commit must pass
        self.cli_commit()

        self.assertTrue(process_named_running(PROCESS_NAME))
        self.assertIn(interface, interfaces())


    def test_openvpn_client_interfaces(self):
        # Create OpenVPN client interfaces connecting to different
        # server IP addresses. Validate configuration afterwards.
        num_range = range(10, 15)
        for ii in num_range:
            interface = f'vtun{ii}'
            remote_host = f'192.0.2.{ii}'
            path = base_path + [interface]
            auth_hash = 'sha1'

            self.cli_set(path + ['device-type', 'tun'])
            self.cli_set(path + ['encryption', 'data-ciphers', 'aes256'])
            self.cli_set(path + ['hash', auth_hash])
            self.cli_set(path + ['mode', 'client'])
            self.cli_set(path + ['persistent-tunnel'])
            self.cli_set(path + ['protocol', protocol])
            self.cli_set(path + ['remote-host', remote_host])
            self.cli_set(path + ['remote-port', remote_port])
            self.cli_set(path + ['tls', 'ca-certificate', 'ovpn_test'])
            self.cli_set(path + ['tls', 'certificate', 'ovpn_test'])
            self.cli_set(path + ['vrf', vrf_name])
            self.cli_set(path + ['authentication', 'username', interface+'user'])
            self.cli_set(path + ['authentication', 'password', interface+'secretpw'])

        self.cli_commit()

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
            self.assertIn(f'data-ciphers AES-256-CBC', config)

            # TLS options
            self.assertIn(f'ca /run/openvpn/{interface}_ca.pem', config)
            self.assertIn(f'cert /run/openvpn/{interface}_cert.pem', config)
            self.assertIn(f'key /run/openvpn/{interface}_cert.key', config)

            self.assertTrue(process_named_running(PROCESS_NAME))
            self.assertEqual(get_vrf(interface), vrf_name)
            self.assertIn(interface, interfaces())

            pw = cmd(f'sudo cat {pw_file}')
            self.assertIn(f'{interface}user', pw)
            self.assertIn(f'{interface}secretpw', pw)

        # check that no interface remained after deleting them
        self.cli_delete(base_path)
        self.cli_commit()

        for ii in num_range:
            interface = f'vtun{ii}'
            self.assertNotIn(interface, interfaces())

    def test_openvpn_server_verify(self):
        # Create one OpenVPN server interface and check required verify() stages
        interface = 'vtun5000'
        path = base_path + [interface]

        # check validate() - must speciy operating mode
        self.cli_set(path)
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(path + ['mode', 'server'])

        # check validate() - cannot specify protocol tcp-active in server mode
        self.cli_set(path + ['protocol', 'tcp-active'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['protocol'])

        # check validate() - cannot specify local-port in client mode
        self.cli_set(path + ['remote-port', '5000'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['remote-port'])

        # check validate() - cannot specify local-host in client mode
        self.cli_set(path + ['remote-host', '127.0.0.1'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['remote-host'])

        # check validate() - must specify "tls dh-params" when not using EC keys
        # in server mode
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(path + ['tls', 'dh-params', 'ovpn_test'])

        # check validate() - must specify "server subnet" or add interface to
        # bridge in server mode
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # check validate() - server client-ip-pool is too large
        # [100.64.0.4 -> 100.127.255.251 = 4194295], maximum is 65536 addresses.
        self.cli_set(path + ['server', 'subnet', '100.64.0.0/10'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # check validate() - cannot specify more than 1 IPv4 and 1 IPv6 server subnet
        self.cli_set(path + ['server', 'subnet', '100.64.0.0/20'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['server', 'subnet', '100.64.0.0/10'])

        # check validate() - must specify "tls ca-certificate"
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(path + ['tls', 'ca-certificate', 'ovpn_test'])

        # check validate() - must specify "tls certificate"
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(path + ['tls', 'certificate', 'ovpn_test'])

        # check validate() - cannot specify "tls role" in client-server mode'
        self.cli_set(path + ['tls', 'role', 'active'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # check validate() - cannot specify "tls role" in client-server mode'
        self.cli_set(path + ['tls', 'auth-key', 'ovpn_test'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # check validate() - cannot specify "tcp-passive" when "tls role" is "active"
        self.cli_set(path + ['protocol', 'tcp-passive'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['protocol'])

        # check validate() - cannot specify "tls dh-params" when "tls role" is "active"
        self.cli_set(path + ['tls', 'dh-params', 'ovpn_test'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['tls', 'dh-params'])

        # check validate() - cannot specify "encryption cipher" in server mode
        self.cli_set(path + ['encryption', 'cipher', 'aes256'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['encryption', 'cipher'])

        # Now test the other path with tls role passive
        self.cli_set(path + ['tls', 'role', 'passive'])
        # check validate() - cannot specify "tcp-active" when "tls role" is "passive"
        self.cli_set(path + ['protocol', 'tcp-active'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['protocol'])

        self.cli_set(path + ['tls', 'dh-params', 'ovpn_test'])

        self.cli_commit()

        self.assertTrue(process_named_running(PROCESS_NAME))
        self.assertIn(interface, interfaces())

    def test_openvpn_server_subnet_topology(self):
        # Create OpenVPN server interfaces using different client subnets.
        # Validate configuration afterwards.

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

            self.cli_set(path + ['device-type', 'tun'])
            self.cli_set(path + ['encryption', 'data-ciphers', 'aes192'])
            self.cli_set(path + ['hash', auth_hash])
            self.cli_set(path + ['mode', 'server'])
            self.cli_set(path + ['local-port', port])
            self.cli_set(path + ['server', 'mfa', 'totp'])
            self.cli_set(path + ['server', 'subnet', subnet])
            self.cli_set(path + ['server', 'topology', 'subnet'])
            self.cli_set(path + ['keep-alive', 'failure-count', '5'])
            self.cli_set(path + ['keep-alive', 'interval', '5'])

            # clients
            self.cli_set(path + ['server', 'client', 'client1', 'ip', client_ip])
            for route in client1_routes:
                self.cli_set(path + ['server', 'client', 'client1', 'subnet', route])

            self.cli_set(path + ['replace-default-route'])
            self.cli_set(path + ['tls', 'ca-certificate', 'ovpn_test'])
            self.cli_set(path + ['tls', 'certificate', 'ovpn_test'])
            self.cli_set(path + ['tls', 'dh-params', 'ovpn_test'])
            self.cli_set(path + ['vrf', vrf_name])

        self.cli_commit()

        for ii in num_range:
            interface = f'vtun{ii}'
            plugin = f'plugin "/usr/lib/openvpn/openvpn-otp.so" "otp_secrets=/config/auth/openvpn/{interface}-otp-secrets otp_slop=180 totp_t0=0 totp_step=30 totp_digits=6 password_is_cr=1"'
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
            self.assertIn(f'data-ciphers AES-192-CBC', config)
            self.assertIn(f'topology subnet', config)
            self.assertIn(f'lport {port}', config)
            self.assertIn(f'push "redirect-gateway def1"', config)
            self.assertIn(f'{plugin}', config)
            self.assertIn(f'keepalive 5 25', config)

            # TLS options
            self.assertIn(f'ca /run/openvpn/{interface}_ca.pem', config)
            self.assertIn(f'cert /run/openvpn/{interface}_cert.pem', config)
            self.assertIn(f'key /run/openvpn/{interface}_cert.key', config)
            self.assertIn(f'dh /run/openvpn/{interface}_dh.pem', config)

            # IP pool configuration
            netmask = IPv4Network(subnet).netmask
            network = IPv4Network(subnet).network_address
            self.assertIn(f'server {network} {netmask}', config)

            # Verify client
            client_config = read_file(client_config_file)

            self.assertIn(f'ifconfig-push {client_ip} {client_netmask}', client_config)
            for route in client1_routes:
                self.assertIn('iroute {} {}'.format(address_from_cidr(route), netmask_from_cidr(route)), client_config)

            self.assertTrue(process_named_running(PROCESS_NAME))
            self.assertEqual(get_vrf(interface), vrf_name)
            self.assertIn(interface, interfaces())

        # check that no interface remained after deleting them
        self.cli_delete(base_path)
        self.cli_commit()

        for ii in num_range:
            interface = f'vtun{ii}'
            self.assertNotIn(interface, interfaces())

    def test_openvpn_site2site_verify(self):
        # Create one OpenVPN site2site interface and check required
        # verify() stages

        interface = 'vtun5000'
        path = base_path + [interface]

        self.cli_set(path + ['mode', 'site-to-site'])

        # check validate() - cipher negotiation cannot be enabled in site-to-site mode
        self.cli_set(path + ['encryption', 'data-ciphers', 'aes192gcm'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['encryption'])

        # check validate() - must specify "local-address" or add interface to bridge
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(path + ['local-address', '10.0.0.1'])
        self.cli_set(path + ['local-address', '2001:db8:1::1'])

        # check validate() - cannot specify more than 1 IPv4 local-address
        self.cli_set(path + ['local-address', '10.0.0.2'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['local-address', '10.0.0.2'])

        # check validate() - cannot specify more than 1 IPv6 local-address
        self.cli_set(path + ['local-address', '2001:db8:1::2'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['local-address', '2001:db8:1::2'])

        # check validate() - IPv4 "local-address" requires IPv4 "remote-address"
        # or IPv4 "local-address subnet"
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(path + ['remote-address', '192.168.0.1'])
        self.cli_set(path + ['remote-address', '2001:db8:ffff::1'])

        # check validate() - Cannot specify more than 1 IPv4 "remote-address"
        self.cli_set(path + ['remote-address', '192.168.0.2'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['remote-address', '192.168.0.2'])

        # check validate() - Cannot specify more than 1 IPv6 "remote-address"
        self.cli_set(path + ['remote-address', '2001:db8:ffff::2'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['remote-address', '2001:db8:ffff::2'])

        # check validate() - Must specify one of "shared-secret-key" and "tls"
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(path + ['shared-secret-key', 'ovpn_test'])

        self.cli_commit()

    def test_openvpn_options(self):
        # Ensure OpenVPN process restart on openvpn-option CLI node change

        interface = 'vtun5001'
        path = base_path + [interface]
        encryption_cipher = 'aes256'

        self.cli_set(path + ['mode', 'site-to-site'])
        self.cli_set(path + ['local-address', '10.0.0.2'])
        self.cli_set(path + ['remote-address', '192.168.0.3'])
        self.cli_set(path + ['shared-secret-key', 'ovpn_test'])
        self.cli_set(path + ['encryption', 'cipher', encryption_cipher])

        self.cli_commit()

        # Now verify the OpenVPN "raw" option passing. Once an openvpn-option is
        # added, modified or deleted from the CLI, OpenVPN daemon must be restarted
        cur_pid = process_named_running('openvpn')
        self.cli_set(path + ['openvpn-option', '--persist-tun'])
        self.cli_commit()

        # PID must be different as OpenVPN Must be restarted
        new_pid = process_named_running('openvpn')
        self.assertNotEqual(cur_pid, new_pid)
        cur_pid = new_pid

        self.cli_set(path + ['openvpn-option', '--persist-key'])
        self.cli_commit()

        # PID must be different as OpenVPN Must be restarted
        new_pid = process_named_running('openvpn')
        self.assertNotEqual(cur_pid, new_pid)
        cur_pid = new_pid

        self.cli_delete(path + ['openvpn-option'])
        self.cli_commit()

        # PID must be different as OpenVPN Must be restarted
        new_pid = process_named_running('openvpn')
        self.assertNotEqual(cur_pid, new_pid)
        cur_pid = new_pid

    def test_openvpn_site2site_interfaces_tun(self):
        # Create two OpenVPN site-to-site interfaces

        num_range = range(30, 35)
        port = ''
        local_address = ''
        remote_address = ''
        encryption_cipher = 'aes256'

        for ii in num_range:
            interface = f'vtun{ii}'
            local_address = f'192.0.{ii}.1'
            local_address_subnet = '255.255.255.252'
            remote_address = f'172.16.{ii}.1'
            path = base_path + [interface]
            port = str(3000 + ii)

            self.cli_set(path + ['local-address', local_address])

            # even numbers use tun type, odd numbers use tap type
            if ii % 2 == 0:
                self.cli_set(path + ['device-type', 'tun'])
            else:
                self.cli_set(path + ['device-type', 'tap'])
                self.cli_set(path + ['local-address', local_address, 'subnet-mask', local_address_subnet])

            self.cli_set(path + ['mode', 'site-to-site'])
            self.cli_set(path + ['local-port', port])
            self.cli_set(path + ['remote-port', port])
            self.cli_set(path + ['shared-secret-key', 'ovpn_test'])
            self.cli_set(path + ['remote-address', remote_address])
            self.cli_set(path + ['encryption', 'cipher', encryption_cipher])
            self.cli_set(path + ['vrf', vrf_name])

        self.cli_commit()

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
            self.assertIn(f'secret /run/openvpn/{interface}_shared.key', config)
            self.assertIn(f'lport {port}', config)
            self.assertIn(f'rport {port}', config)


            self.assertTrue(process_named_running(PROCESS_NAME))
            self.assertEqual(get_vrf(interface), vrf_name)
            self.assertIn(interface, interfaces())


        # check that no interface remained after deleting them
        self.cli_delete(base_path)
        self.cli_commit()

        for ii in num_range:
            interface = f'vtun{ii}'
            self.assertNotIn(interface, interfaces())


    def test_openvpn_server_server_bridge(self):
        # Create OpenVPN server interface using bridge.
        # Validate configuration afterwards.
        br_if = 'br0'
        vtun_if = 'vtun5010'
        auth_hash = 'sha256'
        path = base_path + [vtun_if]
        start_subnet = "192.168.0.100"
        stop_subnet = "192.168.0.200"
        mask_subnet = "255.255.255.0"
        gw_subnet = "192.168.0.1"

        self.cli_set(['interfaces', 'bridge', br_if, 'member', 'interface', vtun_if])
        self.cli_set(path + ['device-type', 'tap'])
        self.cli_set(path + ['encryption', 'data-ciphers', 'aes192'])
        self.cli_set(path + ['hash', auth_hash])
        self.cli_set(path + ['mode', 'server'])
        self.cli_set(path + ['server', 'bridge', 'gateway', gw_subnet])
        self.cli_set(path + ['server', 'bridge', 'start', start_subnet])
        self.cli_set(path + ['server', 'bridge', 'stop', stop_subnet])
        self.cli_set(path + ['server', 'bridge', 'subnet-mask', mask_subnet])
        self.cli_set(path + ['keep-alive', 'failure-count', '5'])
        self.cli_set(path + ['keep-alive', 'interval', '5'])
        self.cli_set(path + ['tls', 'ca-certificate', 'ovpn_test'])
        self.cli_set(path + ['tls', 'certificate', 'ovpn_test'])
        self.cli_set(path + ['tls', 'dh-params', 'ovpn_test'])

        self.cli_commit()

        config_file = f'/run/openvpn/{vtun_if}.conf'
        config = read_file(config_file)
        self.assertIn(f'dev {vtun_if}', config)
        self.assertIn(f'dev-type tap', config)
        self.assertIn(f'proto udp', config) # default protocol
        self.assertIn(f'auth {auth_hash}', config)
        self.assertIn(f'data-ciphers AES-192-CBC', config)
        self.assertIn(f'mode server', config)
        self.assertIn(f'server-bridge {gw_subnet} {mask_subnet} {start_subnet} {stop_subnet}', config)
        self.assertIn(f'keepalive 5 25', config)

        # TLS options
        self.assertIn(f'ca /run/openvpn/{vtun_if}_ca.pem', config)
        self.assertIn(f'cert /run/openvpn/{vtun_if}_cert.pem', config)
        self.assertIn(f'key /run/openvpn/{vtun_if}_cert.key', config)
        self.assertIn(f'dh /run/openvpn/{vtun_if}_dh.pem', config)

        # check that no interface remained after deleting them
        self.cli_delete(['interfaces', 'bridge', br_if, 'member', 'interface', vtun_if])
        self.cli_delete(base_path)
        self.cli_commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
