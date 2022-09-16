#!/usr/bin/env python3
#
# Copyright (C) 2021-2022 VyOS maintainers and contributors
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
from vyos.util import call
from vyos.util import process_named_running
from vyos.util import read_file

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
interface = 'eth1'
vif = '100'
esp_group = 'MyESPGroup'
ike_group = 'MyIKEGroup'
secret = 'MYSECRETKEY'

ca_pem = """
MIIDSzCCAjOgAwIBAgIUQHK+ZgTUYZksvXY2/MyW+Jiels4wDQYJKoZIhvcNAQEL
BQAwFjEUMBIGA1UEAwwLRWFzeS1SU0EgQ0EwHhcNMjEwNjE0MTk0NTI3WhcNMzEw
NjEyMTk0NTI3WjAWMRQwEgYDVQQDDAtFYXN5LVJTQSBDQTCCASIwDQYJKoZIhvcN
AQEBBQADggEPADCCAQoCggEBAKCAzpatA8yywXhGunWD//6Qg9EMJMb+7didNr10
DuYPPGyTOXwG4Xicbr0FJ6cNkWg4wj3ZXEqqBzgS1Z9u78yuYPt5LE9eM8Wtawp7
qIUCMTlSu4uD3/4A3c1xfHDpTOEl1BDvxMtQxQZcMNQVUG5ZMdcWQvqvQG6F7Nak
+jgkaQ+Gyhwq++KVTEHJsA6+POuD0uaqAJv3tLGrRf4y4zdOn4thuTQ9swIBjKW6
ci78Dk0F4u24YYV2BHKsPEPIyCQxKSRrMvqVWWljX9HmNsGawyEhLvW34aphj0aD
JL/n1kWm+DnGyM+Rp6pXQz5y3xAnmKeYziaQNnvHoQi+gY0CAwEAAaOBkDCBjTAd
BgNVHQ4EFgQUy43jkjE+CORrxeddqofQztZ9UxYwUQYDVR0jBEowSIAUy43jkjE+
CORrxeddqofQztZ9UxahGqQYMBYxFDASBgNVBAMMC0Vhc3ktUlNBIENBghRAcr5m
BNRhmSy9djb8zJb4mJ6WzjAMBgNVHRMEBTADAQH/MAsGA1UdDwQEAwIBBjANBgkq
hkiG9w0BAQsFAAOCAQEALHdd1JXq6EUF9dSUijPLEiDVwn2TTIBIxvQqFzpWDDHg
EWLzRJESyNUbIiwuUGwvqcVki0TmQcFR9XwmcDFDotlXz9OQISBlCW+Twuf4/XAL
11njH8qXSaWF/wPbF35NOPhV5xOOCZ6K7Vilp3tK6LeOWvz2AUtwiVE1prNV3cIA
B2ham0JASS0HIkfrcjpZNcx4NlSBaFf4MK5A11p13zPqMqzdEqn6n8fbYEADfVzy
TfdqX1dPVc9zaM8uwyh5VyYBMDV7DoL384ZHJZYLENK/pT4kbl+sM/Cnhvyu0UCe
RVqJGQtCdChZpDAVkzJRQYw3/FR8Mj+M+8GrgOrJ0w==
"""

peer_cert = """
MIIDZjCCAk6gAwIBAgIRAKHpoE0rTcB/YXhnFpeckngwDQYJKoZIhvcNAQELBQAw
FjEUMBIGA1UEAwwLRWFzeS1SU0EgQ0EwHhcNMjEwNjE0MjAwNDQ3WhcNMjQwNTI5
MjAwNDQ3WjAQMQ4wDAYDVQQDDAVwZWVyMTCCASIwDQYJKoZIhvcNAQEBBQADggEP
ADCCAQoCggEBALNwjDC1Lj2ojfCi1TESsyD0MLuqUVLTBZaXCXFtQdB/Aw3b3eBc
J8+FUYQ6xMplmklXcjJEyXSMvqENpLX6xEDNWWvqTf22eEWt36QTfBeyFyDKtXnm
4Y+ufXAHl3sLtyZN/7q+Xl4ubYvtAHVRLYzkXAtj1tVdaYEZQy8x/F3ZFFUsCfxR
RqJBKTxcENP8STpIz9X8dS9iif9SBA42C0eHqMWv1tYW1IHO9gQxYFS3cvoPDPlD
AJ3ihu5x3fO892S7FtZLVN/GsN1TKRKL217eVPyW0+QcnUwbrXWc7fnmm1btXVmh
9YKPdtX8WnEeOtMCVZGKqdydnI3iAqvPmd0CAwEAAaOBtDCBsTAJBgNVHRMEAjAA
MB0GA1UdDgQWBBQGsAPY4cHnTNUv7l+l8OYRSqcX8jBRBgNVHSMESjBIgBTLjeOS
MT4I5GvF512qh9DO1n1TFqEapBgwFjEUMBIGA1UEAwwLRWFzeS1SU0EgQ0GCFEBy
vmYE1GGZLL12NvzMlviYnpbOMBMGA1UdJQQMMAoGCCsGAQUFBwMBMAsGA1UdDwQE
AwIFoDAQBgNVHREECTAHggVwZWVyMTANBgkqhkiG9w0BAQsFAAOCAQEAdJr+11eG
FvChxu/LkwsXe2V+OZzGRq+hmQlaK3kG/AyI5hVA/IVHJkDe281wbBNKBWYxeSMn
lAKbwuhPluO99oldzY9ZVkSiRmLh3r27wy/y+1plvoNxyTN7644Hvtk/8P/LV67R
amXvVgkhpvIQSBfgifXzqUs+BV/x7TSeN3isxNOB8FP6imODsw8lF0Ir1Ze34emr
TMNo5wNR5xp2dUa9OkzjRpgpifh20zM3UeVOixIPoq78IDjT0aZP8Lve2/g4Ccc6
RHNF31r/2UL8rZfQRUAMijVdAvIINCk0kRBhNcr9MCi3czmmgiXXMGwLWLvSkfnE
W06wKX1lpPSptg==
"""

peer_key = """
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQCzcIwwtS49qI3w
otUxErMg9DC7qlFS0wWWlwlxbUHQfwMN293gXCfPhVGEOsTKZZpJV3IyRMl0jL6h
DaS1+sRAzVlr6k39tnhFrd+kE3wXshcgyrV55uGPrn1wB5d7C7cmTf+6vl5eLm2L
7QB1US2M5FwLY9bVXWmBGUMvMfxd2RRVLAn8UUaiQSk8XBDT/Ek6SM/V/HUvYon/
UgQONgtHh6jFr9bWFtSBzvYEMWBUt3L6Dwz5QwCd4obucd3zvPdkuxbWS1TfxrDd
UykSi9te3lT8ltPkHJ1MG611nO355ptW7V1ZofWCj3bV/FpxHjrTAlWRiqncnZyN
4gKrz5ndAgMBAAECggEACvAya4mv3uxWcrPKYSptpvWbvuTb/juE3LAqUDLDz0ze
x8p+VP3pI1pSJMhcVKYq6IufF3df/G3T9Qda4gj+S6D48X4f8PZdkInP1zWk2+Ds
TgBtXZf4agTN+rVLw6FsMbaRfzW5lO4pmV0CKSSgrTUCc2NLpkgCdW8vzEG0y5ek
15uBOyvuydWM4CFgZT/cUvnu4UtPFL1vaTdD4Lw0FfZq4iS8SWsGbbMoTPKkJRlS
k9oMEOvhA1WIfSgiG0FyaidoNEormB6J1SKVo27P8SOYu2etiFdF9SJUYg9cBzM3
z3HcAsXeSh2kpc8Fc2yOS6zI5AsC0Len2SQmKQD8YQKBgQDlgg5cZV5AY2Ji6b+T
nTHjna7dg/kzUOYs0AmK9DHHziZJ2SKucJlB9smynPLjY/MQbKcNWQ1Cad+olDNP
Ts4lLhs4kbITkmgPQME3it1fGstHy/sGcF0m+YRsSxfwt5bxLXH86+d067C0XMhg
URMgGv9ZBTe/P1LuhIUTEjYzlQKBgQDIJvl7sSXHRRB0k7NU/uV3Tut3NTqIzXiz
pq9hMyF+3aIqaA7kdjIIJczv1grVYz+RUdX3Gu1FyHMl8ynoEz5NNWsbe+Ay/moa
ztijak3UH3M+d6WsxSRehdYl6DaMstHwWfKZvWNJCGyl7ckz9gGjc3DY/qYqZDrx
p3LlZsY7KQKBgQCj3ur2GgLkIpI7Yf9CHPlkNlCHJhYnB9pxoNFPf/CTY6R/EiTr
PMaRDO8TM3FR3ynMTmgw5abMBuCFc9v3AqO6dGNHTvBBfUYDrg7H48UQhQckaocA
H/bDP2HIGQ4s+Ek0R2ieWKpZF3iCL8V60CjBwcUVAN6/FS3X1JNX/KbqyQKBgQDA
8dlk5PN/MlPXnZ6t2/7G0bxpsVVZFYI65P+CGvE6RFuUt7VLhalbc10pAtR0unVI
GHTD/iAnOkHOnqeSQiK3+TvkRbluTxVn/GiYt9yJFTxaRqrebzlNKYW0CzOy1JtP
MNaOYCS6/bUHC7//KDKSJ7HsbScwDGlKFVrMTBPiaQKBgQCjkIJDZ4pC3er7QiC3
RXWPyxIG5iTjn4fizphaBt6+pkBAlBh0V6inmleAWa5DJSpgU4jQv4mZsAQs6ctq
usmoy47ke8pTXPHgQ8ZUwsfM4IztqOm+w0X6mSZi6HdJCnMdxCZBBpO225UvonSR
rgiyCHemtMepq57Pl1Nmj49eEA==
"""

class TestVPNIPsec(VyOSUnitTestSHIM.TestCase):
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
        self.assertTrue(process_named_running('charon'))

        self.cli_delete(base_path)
        self.cli_delete(tunnel_path)
        self.cli_commit()

        # Check for no longer running process
        self.assertFalse(process_named_running('charon'))

    def test_01_dhcp_fail_handling(self):
        # Interface for dhcp-interface
        self.cli_set(ethernet_path + [interface, 'vif', vif, 'address', 'dhcp']) # Use VLAN to avoid getting IP from qemu dhcp server

        # Site to site
        peer_base_path = base_path + ['site-to-site', 'peer', connection_name]
        self.cli_set(peer_base_path + ['authentication', 'mode', 'pre-shared-secret'])
        self.cli_set(peer_base_path + ['authentication', 'pre-shared-secret', secret])
        self.cli_set(peer_base_path + ['ike-group', ike_group])
        self.cli_set(peer_base_path + ['default-esp-group', esp_group])
        self.cli_set(peer_base_path + ['dhcp-interface', f'{interface}.{vif}'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'protocol', 'gre'])

        self.cli_commit()

        self.assertTrue(os.path.exists(dhcp_waiting_file))

        dhcp_waiting = read_file(dhcp_waiting_file)
        self.assertIn(f'{interface}.{vif}', dhcp_waiting) # Ensure dhcp-failed interface was added for dhclient hook

    def test_02_site_to_site(self):
        self.cli_set(base_path + ['ike-group', ike_group, 'key-exchange', 'ikev2'])

        # Site to site
        local_address = '192.0.2.10'
        priority = '20'
        life_bytes = '100000'
        life_packets = '2000000'
        peer_base_path = base_path + ['site-to-site', 'peer', connection_name]

        self.cli_set(base_path + ['esp-group', esp_group, 'life-bytes', life_bytes])
        self.cli_set(base_path + ['esp-group', esp_group, 'life-packets', life_packets])

        self.cli_set(peer_base_path + ['authentication', 'mode', 'pre-shared-secret'])
        self.cli_set(peer_base_path + ['authentication', 'pre-shared-secret', secret])
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
            f'id-local = {local_address} # dhcp:no',
            f'id-remote_{peer_ip.replace(".","-")} = {peer_ip}',
            f'secret = "{secret}"'
        ]
        for line in swanctl_secrets_lines:
            self.assertIn(line, swanctl_conf)


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

        # Site to site
        peer_base_path = base_path + ['site-to-site', 'peer', connection_name]
        self.cli_set(peer_base_path + ['authentication', 'mode', 'pre-shared-secret'])
        self.cli_set(peer_base_path + ['authentication', 'pre-shared-secret', secret])
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
            f'id-local = {local_address} # dhcp:no',
            f'id-remote_{peer_ip.replace(".","-")} = {peer_ip}',
            f'secret = "{secret}"'
        ]
        for line in swanctl_secrets_lines:
            self.assertIn(line, swanctl_conf)


    def test_04_dmvpn(self):
        tunnel_if = 'tun100'
        nhrp_secret = 'secret'
        ike_lifetime = '3600'
        esp_lifetime = '1800'

        # Tunnel
        self.cli_set(tunnel_path + [tunnel_if, 'address', '172.16.253.134/29'])
        self.cli_set(tunnel_path + [tunnel_if, 'encapsulation', 'gre'])
        self.cli_set(tunnel_path + [tunnel_if, 'source-address', '192.0.2.1'])
        self.cli_set(tunnel_path + [tunnel_if, 'multicast', 'enable'])
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

        # Profile
        self.cli_set(base_path + ['profile', 'NHRPVPN', 'authentication', 'mode', 'pre-shared-secret'])
        self.cli_set(base_path + ['profile', 'NHRPVPN', 'authentication', 'pre-shared-secret', nhrp_secret])
        self.cli_set(base_path + ['profile', 'NHRPVPN', 'bind', 'tunnel', tunnel_if])
        self.cli_set(base_path + ['profile', 'NHRPVPN', 'esp-group', esp_group])
        self.cli_set(base_path + ['profile', 'NHRPVPN', 'ike-group', ike_group])

        self.cli_commit()

        swanctl_conf = read_file(swanctl_file)
        swanctl_lines = [
            f'proposals = aes128-sha1-modp1024,aes256-sha1-modp1024',
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
        self.cli_set(['pki', 'ca', ca_name, 'certificate', ca_pem.replace('\n','')])
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
        self.cli_set(peer_base_path + ['authentication', 'x509', 'ca-certificate', ca_name])
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

        self.cli_set(peer_base_path + ['authentication', 'local-id', local_id])
        self.cli_set(peer_base_path + ['authentication', 'mode', 'pre-shared-secret'])
        self.cli_set(peer_base_path + ['authentication', 'pre-shared-secret', secret])
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
            f'id-local = {local_address} # dhcp:no',
            f'id-remote_{peer_ip.replace(".","-")} = {peer_ip}',
            f'id-localid = {local_id}',
            f'id-remoteid = {remote_id}',
            f'secret = "{secret}"',
        ]

        for line in swanctl_secrets_lines:
            self.assertIn(line, swanctl_conf)

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
