#!/usr/bin/env python3
#
# Copyright (C) 2021-2023 VyOS maintainers and contributors
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

from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.utils.process import call
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file

ethernet_path = ['interfaces', 'ethernet']
tunnel_path = ['interfaces', 'tunnel']
vti_path = ['interfaces', 'vti']
nhrp_path = ['protocols', 'nhrp']
base_path = ['vpn', 'ipsec']

charon_file = '/etc/strongswan.d/charon.conf'
dhcp_waiting_file = '/tmp/ipsec_dhcp_waiting'
swanctl_file = '/etc/swanctl/swanctl.conf'

peer_ip = '203.0.113.45'
connection_name = 'main-branch'
local_id = 'left'
remote_id = 'right'
interface = 'eth1'
vif = '100'
esp_group = 'MyESPGroup'
ike_group = 'MyIKEGroup'
secret = 'MYSECRETKEY'
PROCESS_NAME = 'charon-systemd'
regex_uuid4 = '[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}'

ca_pem = """
MIICMDCCAdegAwIBAgIUBCzIjYvD7SPbx5oU18IYg7NVxQ0wCgYIKoZIzj0EAwIw
ZzELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNv
bWUtQ2l0eTENMAsGA1UECgwEVnlPUzEgMB4GA1UEAwwXSVBTZWMgU21va2V0ZXN0
IFJvb3QgQ0EwHhcNMjMwOTI0MTIwMzQxWhcNMzMwOTIxMTIwMzQxWjBnMQswCQYD
VQQGEwJHQjETMBEGA1UECAwKU29tZS1TdGF0ZTESMBAGA1UEBwwJU29tZS1DaXR5
MQ0wCwYDVQQKDARWeU9TMSAwHgYDVQQDDBdJUFNlYyBTbW9rZXRlc3QgUm9vdCBD
QTBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABEh8/yU572B3zmFxrGgHk+H7grYt
EHUJodY3gXNWMHz0gySrbGhsGtECDfP/G+T4Suk7cuVzB1wnLocSafD8TcqjYTBf
MA8GA1UdEwEB/wQFMAMBAf8wDgYDVR0PAQH/BAQDAgGGMB0GA1UdJQQWMBQGCCsG
AQUFBwMCBggrBgEFBQcDATAdBgNVHQ4EFgQUTYoQJNlk7X87/gRegHnCnPef39Aw
CgYIKoZIzj0EAwIDRwAwRAIgX1spXjrUc10r3g/Zm4O31LU5O08J2vVqFo94zHE5
0VgCIG4JK9Zg5O/yn4mYksZux7efiHRUzL2y2TXQ9IqrqM8W
"""

int_ca_pem = """
MIICYDCCAgWgAwIBAgIUcFx2BVYErHI+SneyPYHijxXt1cgwCgYIKoZIzj0EAwIw
ZzELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNv
bWUtQ2l0eTENMAsGA1UECgwEVnlPUzEgMB4GA1UEAwwXSVBTZWMgU21va2V0ZXN0
IFJvb3QgQ0EwHhcNMjMwOTI0MTIwNTE5WhcNMzMwOTIwMTIwNTE5WjBvMQswCQYD
VQQGEwJHQjETMBEGA1UECAwKU29tZS1TdGF0ZTESMBAGA1UEBwwJU29tZS1DaXR5
MQ0wCwYDVQQKDARWeU9TMSgwJgYDVQQDDB9JUFNlYyBTbW9rZXRlc3QgSW50ZXJt
ZWRpYXRlIENBMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEIHw2G5dq3c715AcA
tzR++dYu1fLRFmHzRGTZOT7hLrh2Fg4hnKFPLOeUA5Qi50xCvjJ9JnonTyy2RfRH
axYizKOBhjCBgzASBgNVHRMBAf8ECDAGAQH/AgEAMA4GA1UdDwEB/wQEAwIBhjAd
BgNVHSUEFjAUBggrBgEFBQcDAgYIKwYBBQUHAwEwHQYDVR0OBBYEFC9KrFYtA+hO
l7vdMbWxTMAyLB7BMB8GA1UdIwQYMBaAFE2KECTZZO1/O/4EXoB5wpz3n9/QMAoG
CCqGSM49BAMCA0kAMEYCIQCnqWbElgOL9dGO3iLxasFNq/hM7vM/DzaiHi4BowxW
0gIhAMohefNj+QgLfPhvyODHIPE9LMyfp7lJEaCC2K8PCSFD
"""

peer_cert = """
MIICSTCCAfCgAwIBAgIUPxYleUgCo/glVVePze3QmAFgi6MwCgYIKoZIzj0EAwIw
bzELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNv
bWUtQ2l0eTENMAsGA1UECgwEVnlPUzEoMCYGA1UEAwwfSVBTZWMgU21va2V0ZXN0
IEludGVybWVkaWF0ZSBDQTAeFw0yMzA5MjQxMjA2NDJaFw0yODA5MjIxMjA2NDJa
MGQxCzAJBgNVBAYTAkdCMRMwEQYDVQQIDApTb21lLVN0YXRlMRIwEAYDVQQHDAlT
b21lLUNpdHkxDTALBgNVBAoMBFZ5T1MxHTAbBgNVBAMMFElQU2VjIFNtb2tldGVz
dCBQZWVyMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEZJtuTDu84uy++GMwRNLl
10JAXZxXQSDl+CdTWwjbQZURcdY+ia7BoaoYX/0VKPel3Se64rIUQQLQoY/9MJb9
UKN1MHMwDAYDVR0TAQH/BAIwADAOBgNVHQ8BAf8EBAMCB4AwEwYDVR0lBAwwCgYI
KwYBBQUHAwEwHQYDVR0OBBYEFNJCdnkm3cAmf04UwOKL7IqMJ6OXMB8GA1UdIwQY
MBaAFC9KrFYtA+hOl7vdMbWxTMAyLB7BMAoGCCqGSM49BAMCA0cAMEQCIGVnDRUy
UJ0U/deDvrBo1+AakZndkNAMN/XNo5a5GzhEAiBCY7E/3b0BIO8FiIbVB3iDcaxg
g7ET2RgWxvhEoN3ZRw==
"""

peer_key = """
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgVDEZDK7q/T+tiJUV
WLKS3ZYDfZ4lZv0C1gJpYq0gWP2hRANCAARkm25MO7zi7L74YzBE0uXXQkBdnFdB
IOX4J1NbCNtBlRFx1j6JrsGhqhhf/RUo96XdJ7rishRBAtChj/0wlv1Q
"""

swanctl_dir = '/etc/swanctl'
CERT_PATH   = f'{swanctl_dir}/x509/'
CA_PATH     = f'{swanctl_dir}/x509ca/'

class TestVPNIPsec(VyOSUnitTestSHIM.TestCase):
    skip_process_check = False

    @classmethod
    def setUpClass(cls):
        super(TestVPNIPsec, cls).setUpClass()
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

        cls.cli_set(cls, base_path + ['interface', f'{interface}.{vif}'])

    @classmethod
    def tearDownClass(cls):
        super(TestVPNIPsec, cls).tearDownClass()
        cls.cli_delete(cls, base_path + ['interface', f'{interface}.{vif}'])

    def setUp(self):
        # Set IKE/ESP Groups
        self.cli_set(base_path + ['esp-group', esp_group, 'proposal', '1', 'encryption', 'aes128'])
        self.cli_set(base_path + ['esp-group', esp_group, 'proposal', '1', 'hash', 'sha1'])
        self.cli_set(base_path + ['ike-group', ike_group, 'proposal', '1', 'dh-group', '2'])
        self.cli_set(base_path + ['ike-group', ike_group, 'proposal', '1', 'encryption', 'aes128'])
        self.cli_set(base_path + ['ike-group', ike_group, 'proposal', '1', 'hash', 'sha1'])

    def tearDown(self):
        # Check for running process
        if not self.skip_process_check:
            self.assertTrue(process_named_running(PROCESS_NAME))
        else:
            self.skip_process_check = False # Reset

        self.cli_delete(base_path)
        self.cli_delete(tunnel_path)
        self.cli_commit()

        # Check for no longer running process
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_01_dhcp_fail_handling(self):
        # Skip process check - connection is not created for this test
        self.skip_process_check = True

        # Interface for dhcp-interface
        self.cli_set(ethernet_path + [interface, 'vif', vif, 'address', 'dhcp']) # Use VLAN to avoid getting IP from qemu dhcp server

        # vpn ipsec auth psk <tag> id <x.x.x.x>
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'id', local_id])
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'id', remote_id])
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'id', peer_ip])
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'secret', secret])

        # Site to site
        peer_base_path = base_path + ['site-to-site', 'peer', connection_name]
        self.cli_set(peer_base_path + ['authentication', 'mode', 'pre-shared-secret'])
        self.cli_set(peer_base_path + ['ike-group', ike_group])
        self.cli_set(peer_base_path + ['default-esp-group', esp_group])
        self.cli_set(peer_base_path + ['dhcp-interface', f'{interface}.{vif}'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'protocol', 'gre'])

        self.cli_commit()

        self.assertTrue(os.path.exists(dhcp_waiting_file))

        dhcp_waiting = read_file(dhcp_waiting_file)
        self.assertIn(f'{interface}.{vif}', dhcp_waiting) # Ensure dhcp-failed interface was added for dhclient hook

        self.cli_delete(ethernet_path + [interface, 'vif', vif, 'address'])

    def test_02_site_to_site(self):
        self.cli_set(base_path + ['ike-group', ike_group, 'key-exchange', 'ikev2'])

        local_address = '192.0.2.10'
        priority = '20'
        life_bytes = '100000'
        life_packets = '2000000'

        # vpn ipsec auth psk <tag> id <x.x.x.x>
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'id', local_id])
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'id', remote_id])
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'id', local_address])
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'id', peer_ip])
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'secret', secret])

        # Site to site
        peer_base_path = base_path + ['site-to-site', 'peer', connection_name]

        self.cli_set(base_path + ['esp-group', esp_group, 'life-bytes', life_bytes])
        self.cli_set(base_path + ['esp-group', esp_group, 'life-packets', life_packets])

        self.cli_set(peer_base_path + ['authentication', 'mode', 'pre-shared-secret'])
        self.cli_set(peer_base_path + ['ike-group', ike_group])
        self.cli_set(peer_base_path + ['default-esp-group', esp_group])
        self.cli_set(peer_base_path + ['local-address', local_address])
        self.cli_set(peer_base_path + ['remote-address', peer_ip])
        self.cli_set(peer_base_path + ['tunnel', '1', 'protocol', 'tcp'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'local', 'prefix', '172.16.10.0/24'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'local', 'prefix', '172.16.11.0/24'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'local', 'port', '443'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'remote', 'prefix', '172.17.10.0/24'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'remote', 'prefix', '172.17.11.0/24'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'remote', 'port', '443'])

        self.cli_set(peer_base_path + ['tunnel', '2', 'local', 'prefix', '10.1.0.0/16'])
        self.cli_set(peer_base_path + ['tunnel', '2', 'remote', 'prefix', '10.2.0.0/16'])
        self.cli_set(peer_base_path + ['tunnel', '2', 'priority', priority])

        self.cli_commit()

        # Verify strongSwan configuration
        swanctl_conf = read_file(swanctl_file)
        swanctl_conf_lines = [
            f'version = 2',
            f'auth = psk',
            f'life_bytes = {life_bytes}',
            f'life_packets = {life_packets}',
            f'rekey_time = 28800s', # default value
            f'proposals = aes128-sha1-modp1024',
            f'esp_proposals = aes128-sha1-modp1024',
            f'life_time = 3600s', # default value
            f'local_addrs = {local_address} # dhcp:no',
            f'remote_addrs = {peer_ip}',
            f'mode = tunnel',
            f'{connection_name}-tunnel-1',
            f'local_ts = 172.16.10.0/24[tcp/443],172.16.11.0/24[tcp/443]',
            f'remote_ts = 172.17.10.0/24[tcp/443],172.17.11.0/24[tcp/443]',
            f'mode = tunnel',
            f'{connection_name}-tunnel-2',
            f'local_ts = 10.1.0.0/16',
            f'remote_ts = 10.2.0.0/16',
            f'priority = {priority}',
            f'mode = tunnel',
        ]
        for line in swanctl_conf_lines:
            self.assertIn(line, swanctl_conf)

        swanctl_secrets_lines = [
            f'id-{regex_uuid4} = "{local_id}"',
            f'id-{regex_uuid4} = "{remote_id}"',
            f'id-{regex_uuid4} = "{local_address}"',
            f'id-{regex_uuid4} = "{peer_ip}"',
            f'secret = "{secret}"'
        ]
        for line in swanctl_secrets_lines:
            self.assertRegex(swanctl_conf, fr'{line}')


    def test_03_site_to_site_vti(self):
        local_address = '192.0.2.10'
        vti = 'vti10'
        # IKE
        self.cli_set(base_path + ['ike-group', ike_group, 'key-exchange', 'ikev2'])
        self.cli_set(base_path + ['ike-group', ike_group, 'disable-mobike'])
        # ESP
        self.cli_set(base_path + ['esp-group', esp_group, 'compression'])
        # VTI interface
        self.cli_set(vti_path + [vti, 'address', '10.1.1.1/24'])

        # vpn ipsec auth psk <tag> id <x.x.x.x>
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'id', local_id])
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'id', remote_id])
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'id', peer_ip])
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'secret', secret])

        # Site to site
        peer_base_path = base_path + ['site-to-site', 'peer', connection_name]
        self.cli_set(peer_base_path + ['authentication', 'mode', 'pre-shared-secret'])
        self.cli_set(peer_base_path + ['connection-type', 'none'])
        self.cli_set(peer_base_path + ['force-udp-encapsulation'])
        self.cli_set(peer_base_path + ['ike-group', ike_group])
        self.cli_set(peer_base_path + ['default-esp-group', esp_group])
        self.cli_set(peer_base_path + ['local-address', local_address])
        self.cli_set(peer_base_path + ['remote-address', peer_ip])
        self.cli_set(peer_base_path + ['tunnel', '1', 'local', 'prefix', '172.16.10.0/24'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'local', 'prefix', '172.16.11.0/24'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'remote', 'prefix', '172.17.10.0/24'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'remote', 'prefix', '172.17.11.0/24'])
        self.cli_set(peer_base_path + ['vti', 'bind', vti])
        self.cli_set(peer_base_path + ['vti', 'esp-group', esp_group])

        self.cli_commit()

        swanctl_conf = read_file(swanctl_file)
        if_id = vti.lstrip('vti')
        # The key defaults to 0 and will match any policies which similarly do
        # not have a lookup key configuration - thus we shift the key by one
        # to also support a vti0 interface
        if_id = str(int(if_id) +1)
        swanctl_conf_lines = [
            f'version = 2',
            f'auth = psk',
            f'proposals = aes128-sha1-modp1024',
            f'esp_proposals = aes128-sha1-modp1024',
            f'local_addrs = {local_address} # dhcp:no',
            f'mobike = no',
            f'remote_addrs = {peer_ip}',
            f'mode = tunnel',
            f'local_ts = 172.16.10.0/24,172.16.11.0/24',
            f'remote_ts = 172.17.10.0/24,172.17.11.0/24',
            f'ipcomp = yes',
            f'start_action = none',
            f'if_id_in = {if_id}', # will be 11 for vti10 - shifted by one
            f'if_id_out = {if_id}',
            f'updown = "/etc/ipsec.d/vti-up-down {vti}"'
        ]
        for line in swanctl_conf_lines:
            self.assertIn(line, swanctl_conf)

        swanctl_secrets_lines = [
            f'id-{regex_uuid4} = "{local_id}"',
            f'id-{regex_uuid4} = "{remote_id}"',
            f'secret = "{secret}"'
        ]
        for line in swanctl_secrets_lines:
            self.assertRegex(swanctl_conf, fr'{line}')


    def test_04_dmvpn(self):
        tunnel_if = 'tun100'
        nhrp_secret = 'secret'
        ike_lifetime = '3600'
        esp_lifetime = '1800'

        # Tunnel
        self.cli_set(tunnel_path + [tunnel_if, 'address', '172.16.253.134/29'])
        self.cli_set(tunnel_path + [tunnel_if, 'encapsulation', 'gre'])
        self.cli_set(tunnel_path + [tunnel_if, 'source-address', '192.0.2.1'])
        self.cli_set(tunnel_path + [tunnel_if, 'enable-multicast'])
        self.cli_set(tunnel_path + [tunnel_if, 'parameters', 'ip', 'key', '1'])

        # NHRP
        self.cli_set(nhrp_path + ['tunnel', tunnel_if, 'cisco-authentication', nhrp_secret])
        self.cli_set(nhrp_path + ['tunnel', tunnel_if, 'holding-time', '300'])
        self.cli_set(nhrp_path + ['tunnel', tunnel_if, 'multicast', 'dynamic'])
        self.cli_set(nhrp_path + ['tunnel', tunnel_if, 'redirect'])
        self.cli_set(nhrp_path + ['tunnel', tunnel_if, 'shortcut'])

        # IKE/ESP Groups
        self.cli_set(base_path + ['esp-group', esp_group, 'lifetime', esp_lifetime])
        self.cli_set(base_path + ['esp-group', esp_group, 'mode', 'transport'])
        self.cli_set(base_path + ['esp-group', esp_group, 'pfs', 'dh-group2'])
        self.cli_set(base_path + ['esp-group', esp_group, 'proposal', '2', 'encryption', 'aes256'])
        self.cli_set(base_path + ['esp-group', esp_group, 'proposal', '2', 'hash', 'sha1'])
        self.cli_set(base_path + ['esp-group', esp_group, 'proposal', '3', 'encryption', '3des'])
        self.cli_set(base_path + ['esp-group', esp_group, 'proposal', '3', 'hash', 'md5'])

        self.cli_set(base_path + ['ike-group', ike_group, 'key-exchange', 'ikev1'])
        self.cli_set(base_path + ['ike-group', ike_group, 'lifetime', ike_lifetime])
        self.cli_set(base_path + ['ike-group', ike_group, 'proposal', '2', 'dh-group', '2'])
        self.cli_set(base_path + ['ike-group', ike_group, 'proposal', '2', 'encryption', 'aes256'])
        self.cli_set(base_path + ['ike-group', ike_group, 'proposal', '2', 'hash', 'sha1'])
        self.cli_set(base_path + ['ike-group', ike_group, 'proposal', '2', 'prf', 'prfsha1'])

        # Profile
        self.cli_set(base_path + ['profile', 'NHRPVPN', 'authentication', 'mode', 'pre-shared-secret'])
        self.cli_set(base_path + ['profile', 'NHRPVPN', 'authentication', 'pre-shared-secret', nhrp_secret])
        self.cli_set(base_path + ['profile', 'NHRPVPN', 'bind', 'tunnel', tunnel_if])
        self.cli_set(base_path + ['profile', 'NHRPVPN', 'esp-group', esp_group])
        self.cli_set(base_path + ['profile', 'NHRPVPN', 'ike-group', ike_group])

        self.cli_commit()

        swanctl_conf = read_file(swanctl_file)
        swanctl_lines = [
            f'proposals = aes128-sha1-modp1024,aes256-sha1-prfsha1-modp1024',
            f'version = 1',
            f'rekey_time = {ike_lifetime}s',
            f'rekey_time = {esp_lifetime}s',
            f'esp_proposals = aes128-sha1-modp1024,aes256-sha1-modp1024,3des-md5-modp1024',
            f'local_ts = dynamic[gre]',
            f'remote_ts = dynamic[gre]',
            f'mode = transport',
            f'secret = {nhrp_secret}'
        ]
        for line in swanctl_lines:
            self.assertIn(line, swanctl_conf)

        # There is only one NHRP test so no need to delete this globally in tearDown()
        self.cli_delete(nhrp_path)

    def test_05_x509_site2site(self):
        # Enable PKI
        peer_name = 'peer1'
        ca_name = 'MyVyOS-CA'
        int_ca_name = 'MyVyOS-IntCA'
        self.cli_set(['pki', 'ca', ca_name, 'certificate', ca_pem.replace('\n','')])
        self.cli_set(['pki', 'ca', int_ca_name, 'certificate', int_ca_pem.replace('\n','')])
        self.cli_set(['pki', 'certificate', peer_name, 'certificate', peer_cert.replace('\n','')])
        self.cli_set(['pki', 'certificate', peer_name, 'private', 'key', peer_key.replace('\n','')])

        vti = 'vti20'
        self.cli_set(vti_path + [vti, 'address', '192.168.0.1/31'])

        peer_ip = '172.18.254.202'
        connection_name = 'office'
        local_address = '172.18.254.201'
        peer_base_path = base_path + ['site-to-site', 'peer', connection_name]

        self.cli_set(peer_base_path + ['authentication', 'local-id', peer_name])
        self.cli_set(peer_base_path + ['authentication', 'mode', 'x509'])
        self.cli_set(peer_base_path + ['authentication', 'remote-id', 'peer2'])
        self.cli_set(peer_base_path + ['authentication', 'x509', 'ca-certificate', int_ca_name])
        self.cli_set(peer_base_path + ['authentication', 'x509', 'certificate', peer_name])
        self.cli_set(peer_base_path + ['connection-type', 'initiate'])
        self.cli_set(peer_base_path + ['ike-group', ike_group])
        self.cli_set(peer_base_path + ['ikev2-reauth', 'inherit'])
        self.cli_set(peer_base_path + ['local-address', local_address])
        self.cli_set(peer_base_path + ['remote-address', peer_ip])
        self.cli_set(peer_base_path + ['vti', 'bind', vti])
        self.cli_set(peer_base_path + ['vti', 'esp-group', esp_group])

        self.cli_commit()

        swanctl_conf = read_file(swanctl_file)
        tmp = peer_ip.replace('.', '-')
        if_id = vti.lstrip('vti')
        # The key defaults to 0 and will match any policies which similarly do
        # not have a lookup key configuration - thus we shift the key by one
        # to also support a vti0 interface
        if_id = str(int(if_id) +1)
        swanctl_lines = [
            f'{connection_name}',
            f'version = 0', # key-exchange not set - defaulting to 0 for ikev1 and ikev2
            f'send_cert = always',
            f'mobike = yes',
            f'keyingtries = 0',
            f'id = "{peer_name}"',
            f'auth = pubkey',
            f'certs = {peer_name}.pem',
            f'proposals = aes128-sha1-modp1024',
            f'esp_proposals = aes128-sha1-modp1024',
            f'local_addrs = {local_address} # dhcp:no',
            f'remote_addrs = {peer_ip}',
            f'local_ts = 0.0.0.0/0,::/0',
            f'remote_ts = 0.0.0.0/0,::/0',
            f'updown = "/etc/ipsec.d/vti-up-down {vti}"',
            f'if_id_in = {if_id}', # will be 11 for vti10
            f'if_id_out = {if_id}',
            f'ipcomp = no',
            f'mode = tunnel',
            f'start_action = start',
        ]
        for line in swanctl_lines:
            self.assertIn(line, swanctl_conf)

        swanctl_secrets_lines = [
            f'{connection_name}',
            f'file = {peer_name}.pem',
        ]
        for line in swanctl_secrets_lines:
            self.assertIn(line, swanctl_conf)

        # Check Root CA, Intermediate CA and Peer cert/key pair is present
        self.assertTrue(os.path.exists(os.path.join(CA_PATH, f'{int_ca_name}_1.pem')))
        self.assertTrue(os.path.exists(os.path.join(CA_PATH, f'{int_ca_name}_2.pem')))
        self.assertTrue(os.path.exists(os.path.join(CERT_PATH, f'{peer_name}.pem')))

        # There is only one VTI test so no need to delete this globally in tearDown()
        self.cli_delete(vti_path)


    def test_06_flex_vpn_vips(self):
        local_address = '192.0.2.5'
        local_id = 'vyos-r1'
        remote_id = 'vyos-r2'
        peer_base_path = base_path + ['site-to-site', 'peer', connection_name]

        self.cli_set(tunnel_path + ['tun1', 'encapsulation', 'gre'])
        self.cli_set(tunnel_path + ['tun1', 'source-address', local_address])

        self.cli_set(base_path + ['interface', interface])
        self.cli_set(base_path + ['options', 'flexvpn'])
        self.cli_set(base_path + ['options', 'interface', 'tun1'])
        self.cli_set(base_path + ['ike-group', ike_group, 'key-exchange', 'ikev2'])

        # vpn ipsec auth psk <tag> id <x.x.x.x>
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'id', local_id])
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'id', remote_id])
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'id', local_address])
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'id', peer_ip])
        self.cli_set(base_path + ['authentication', 'psk', connection_name, 'secret', secret])

        self.cli_set(peer_base_path + ['authentication', 'local-id', local_id])
        self.cli_set(peer_base_path + ['authentication', 'mode', 'pre-shared-secret'])
        self.cli_set(peer_base_path + ['authentication', 'remote-id', remote_id])
        self.cli_set(peer_base_path + ['connection-type', 'initiate'])
        self.cli_set(peer_base_path + ['ike-group', ike_group])
        self.cli_set(peer_base_path + ['default-esp-group', esp_group])
        self.cli_set(peer_base_path + ['local-address', local_address])
        self.cli_set(peer_base_path + ['remote-address', peer_ip])
        self.cli_set(peer_base_path + ['tunnel', '1', 'protocol', 'gre'])

        self.cli_set(peer_base_path + ['virtual-address', '203.0.113.55'])
        self.cli_set(peer_base_path + ['virtual-address', '203.0.113.56'])

        self.cli_commit()

        # Verify strongSwan configuration
        swanctl_conf = read_file(swanctl_file)
        swanctl_conf_lines = [
            f'version = 2',
            f'vips = 203.0.113.55, 203.0.113.56',
            f'life_time = 3600s', # default value
            f'local_addrs = {local_address} # dhcp:no',
            f'remote_addrs = {peer_ip}',
            f'{connection_name}-tunnel-1',
            f'mode = tunnel',
        ]

        for line in swanctl_conf_lines:
            self.assertIn(line, swanctl_conf)

        swanctl_secrets_lines = [
            f'id-{regex_uuid4} = "{local_id}"',
            f'id-{regex_uuid4} = "{remote_id}"',
            f'id-{regex_uuid4} = "{peer_ip}"',
            f'id-{regex_uuid4} = "{local_address}"',
            f'secret = "{secret}"',
        ]

        for line in swanctl_secrets_lines:
            self.assertRegex(swanctl_conf, fr'{line}')

        # Verify charon configuration
        charon_conf = read_file(charon_file)
        charon_conf_lines = [
            f'# Cisco FlexVPN',
            f'cisco_flexvpn = yes',
            f'install_virtual_ip = yes',
            f'install_virtual_ip_on = tun1',
        ]

        for line in charon_conf_lines:
            self.assertIn(line, charon_conf)


if __name__ == '__main__':
    unittest.main(verbosity=2)
