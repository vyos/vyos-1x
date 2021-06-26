#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

from vyos.util import call, process_named_running, read_file

ethernet_path = ['interfaces', 'ethernet']
tunnel_path = ['interfaces', 'tunnel']
vti_path = ['interfaces', 'vti']
nhrp_path = ['protocols', 'nhrp']
base_path = ['vpn', 'ipsec']

dhcp_waiting_file = '/tmp/ipsec_dhcp_waiting'
swanctl_file = '/etc/swanctl/swanctl.conf'

class TestVPNIPsec(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_delete(nhrp_path)
        self.cli_delete(tunnel_path)
        self.cli_delete(vti_path)
        self.cli_delete(ethernet_path)
        self.cli_commit()

    def test_dhcp_fail_handling(self):
        self.cli_delete(ethernet_path)
        self.cli_delete(base_path)

        # Interface for dhcp-interface
        self.cli_set(ethernet_path + ['eth0', 'vif', '100', 'address', 'dhcp']) # Use VLAN to avoid getting IP from qemu dhcp server

        # Set IKE/ESP Groups
        self.cli_set(base_path + ["esp-group", "MyESPGroup", "proposal", "1", "encryption", "aes128"])
        self.cli_set(base_path + ["esp-group", "MyESPGroup", "proposal", "1", "hash", "sha1"])
        self.cli_set(base_path + ["ike-group", "MyIKEGroup", "proposal", "1", "dh-group", "2"])
        self.cli_set(base_path + ["ike-group", "MyIKEGroup", "proposal", "1", "encryption", "aes128"])
        self.cli_set(base_path + ["ike-group", "MyIKEGroup", "proposal", "1", "hash", "sha1"])

        # Site to site
        self.cli_set(base_path + ["ipsec-interfaces", "interface", "eth0.100"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "authentication", "mode", "pre-shared-secret"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "authentication", "pre-shared-secret", "MYSECRETKEY"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "ike-group", "MyIKEGroup"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "default-esp-group", "MyESPGroup"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "dhcp-interface", "eth0.100"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "tunnel", "1", "protocol", "gre"])

        self.cli_commit()

        self.assertTrue(os.path.exists(dhcp_waiting_file))

        dhcp_waiting = read_file(dhcp_waiting_file)
        self.assertIn('eth0.100', dhcp_waiting) # Ensure dhcp-failed interface was added for dhclient hook

        self.assertTrue(process_named_running('charon')) # Commit should've still succeeded and launched charon

    def test_site_to_site(self):
        self.cli_delete(base_path)

        # IKE/ESP Groups
        self.cli_set(base_path + ["esp-group", "MyESPGroup", "proposal", "1", "encryption", "aes128"])
        self.cli_set(base_path + ["esp-group", "MyESPGroup", "proposal", "1", "hash", "sha1"])
        self.cli_set(base_path + ["ike-group", "MyIKEGroup", "proposal", "1", "dh-group", "2"])
        self.cli_set(base_path + ["ike-group", "MyIKEGroup", "proposal", "1", "encryption", "aes128"])
        self.cli_set(base_path + ["ike-group", "MyIKEGroup", "proposal", "1", "hash", "sha1"])
        self.cli_set(base_path + ["ike-group", "MyIKEGroup", "key-exchange", "ikev2"])

        # Site to site
        self.cli_set(base_path + ["ipsec-interfaces", "interface", "eth0"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "authentication", "mode", "pre-shared-secret"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "authentication", "pre-shared-secret", "MYSECRETKEY"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "ike-group", "MyIKEGroup"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "default-esp-group", "MyESPGroup"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "local-address", "192.0.2.10"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "tunnel", "1", "protocol", "tcp"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "tunnel", "1", "local", "prefix", "172.16.10.0/24"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "tunnel", "1", "local", "prefix", "172.16.11.0/24"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "tunnel", "1", "local", "port", "443"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "tunnel", "1", "remote", "prefix", "172.17.10.0/24"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "tunnel", "1", "remote", "prefix", "172.17.11.0/24"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "tunnel", "1", "remote", "port", "443"])

        self.cli_commit()

        swanctl_conf_lines = [
            'version = 2',
            'auth = psk',
            'proposals = aes128-sha1-modp1024',
            'esp_proposals = aes128-sha1-modp1024',
            'local_addrs = 192.0.2.10 # dhcp:no',
            'remote_addrs = 203.0.113.45',
            'mode = tunnel',
            'local_ts = 172.16.10.0/24[tcp/443],172.16.11.0/24[tcp/443]',
            'remote_ts = 172.17.10.0/24[tcp/443],172.17.11.0/24[tcp/443]'
        ]

        swanctl_secrets_lines = [
            'id-local = 192.0.2.10 # dhcp:no',
            'id-remote = 203.0.113.45',
            'secret = "MYSECRETKEY"'
        ]

        tmp_swanctl_conf = read_file(swanctl_file)

        for line in swanctl_conf_lines:
            self.assertIn(line, tmp_swanctl_conf)

        for line in swanctl_secrets_lines:
            self.assertIn(line, tmp_swanctl_conf)

        # Check for running process
        self.assertTrue(process_named_running('charon'))

    def test_site_to_site_vti(self):
        self.cli_delete(base_path)
        self.cli_delete(vti_path)

        # VTI interface
        self.cli_set(vti_path + ["vti10", "address", "10.1.1.1/24"])

        # IKE/ESP Groups
        self.cli_set(base_path + ["esp-group", "MyESPGroup", "proposal", "1", "encryption", "aes128"])
        self.cli_set(base_path + ["esp-group", "MyESPGroup", "proposal", "1", "hash", "sha1"])
        self.cli_set(base_path + ["ike-group", "MyIKEGroup", "proposal", "1", "dh-group", "2"])
        self.cli_set(base_path + ["ike-group", "MyIKEGroup", "proposal", "1", "encryption", "aes128"])
        self.cli_set(base_path + ["ike-group", "MyIKEGroup", "proposal", "1", "hash", "sha1"])
        self.cli_set(base_path + ["ike-group", "MyIKEGroup", "key-exchange", "ikev2"])

        # Site to site
        self.cli_set(base_path + ["ipsec-interfaces", "interface", "eth0"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "authentication", "mode", "pre-shared-secret"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "authentication", "pre-shared-secret", "MYSECRETKEY"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "ike-group", "MyIKEGroup"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "default-esp-group", "MyESPGroup"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "local-address", "192.0.2.10"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "tunnel", "1", "local", "prefix", "172.16.10.0/24"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "tunnel", "1", "local", "prefix", "172.16.11.0/24"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "tunnel", "1", "remote", "prefix", "172.17.10.0/24"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "tunnel", "1", "remote", "prefix", "172.17.11.0/24"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "vti", "bind", "vti10"])
        self.cli_set(base_path + ["site-to-site", "peer", "203.0.113.45", "vti", "esp-group", "MyESPGroup"])

        self.cli_commit()

        swanctl_conf_lines = [
            'version = 2',
            'auth = psk',
            'proposals = aes128-sha1-modp1024',
            'esp_proposals = aes128-sha1-modp1024',
            'local_addrs = 192.0.2.10 # dhcp:no',
            'remote_addrs = 203.0.113.45',
            'mode = tunnel',
            'local_ts = 172.16.10.0/24,172.16.11.0/24',
            'remote_ts = 172.17.10.0/24,172.17.11.0/24',
            'mark_in = 9437194', # 0x900000 + (vti)10
            'mark_out = 9437194',
            'updown = "/etc/ipsec.d/vti-up-down vti10 no"'
        ]

        swanctl_secrets_lines = [
            'id-local = 192.0.2.10 # dhcp:no',
            'id-remote = 203.0.113.45',
            'secret = "MYSECRETKEY"'
        ]

        tmp_swanctl_conf = read_file(swanctl_file)

        for line in swanctl_conf_lines:
            self.assertIn(line, tmp_swanctl_conf)

        for line in swanctl_secrets_lines:
            self.assertIn(line, tmp_swanctl_conf)

        # Check for running process
        self.assertTrue(process_named_running('charon'))

    def test_dmvpn(self):
        self.cli_delete(base_path)
        self.cli_delete(nhrp_path)
        self.cli_delete(tunnel_path)

        # Tunnel
        self.cli_set(tunnel_path + ["tun100", "address", "172.16.253.134/29"])
        self.cli_set(tunnel_path + ["tun100", "encapsulation", "gre"])
        self.cli_set(tunnel_path + ["tun100", "source-address", "192.0.2.1"])
        self.cli_set(tunnel_path + ["tun100", "multicast", "enable"])
        self.cli_set(tunnel_path + ["tun100", "parameters", "ip", "key", "1"])

        # NHRP
        self.cli_set(nhrp_path + ["tunnel", "tun100", "cisco-authentication", "secret"])
        self.cli_set(nhrp_path + ["tunnel", "tun100", "holding-time", "300"])
        self.cli_set(nhrp_path + ["tunnel", "tun100", "multicast", "dynamic"])
        self.cli_set(nhrp_path + ["tunnel", "tun100", "redirect"])
        self.cli_set(nhrp_path + ["tunnel", "tun100", "shortcut"])

        # IKE/ESP Groups
        self.cli_set(base_path + ["esp-group", "ESP-HUB", "compression", "disable"])
        self.cli_set(base_path + ["esp-group", "ESP-HUB", "lifetime", "1800"])
        self.cli_set(base_path + ["esp-group", "ESP-HUB", "mode", "transport"])
        self.cli_set(base_path + ["esp-group", "ESP-HUB", "pfs", "dh-group2"])
        self.cli_set(base_path + ["esp-group", "ESP-HUB", "proposal", "1", "encryption", "aes256"])
        self.cli_set(base_path + ["esp-group", "ESP-HUB", "proposal", "1", "hash", "sha1"])
        self.cli_set(base_path + ["esp-group", "ESP-HUB", "proposal", "2", "encryption", "3des"])
        self.cli_set(base_path + ["esp-group", "ESP-HUB", "proposal", "2", "hash", "md5"])
        self.cli_set(base_path + ["ike-group", "IKE-HUB", "ikev2-reauth", "no"])
        self.cli_set(base_path + ["ike-group", "IKE-HUB", "key-exchange", "ikev1"])
        self.cli_set(base_path + ["ike-group", "IKE-HUB", "lifetime", "3600"])
        self.cli_set(base_path + ["ike-group", "IKE-HUB", "proposal", "1", "dh-group", "2"])
        self.cli_set(base_path + ["ike-group", "IKE-HUB", "proposal", "1", "encryption", "aes256"])
        self.cli_set(base_path + ["ike-group", "IKE-HUB", "proposal", "1", "hash", "sha1"])
        self.cli_set(base_path + ["ike-group", "IKE-HUB", "proposal", "2", "dh-group", "2"])
        self.cli_set(base_path + ["ike-group", "IKE-HUB", "proposal", "2", "encryption", "aes128"])
        self.cli_set(base_path + ["ike-group", "IKE-HUB", "proposal", "2", "hash", "sha1"])

        # Profile
        self.cli_set(base_path + ["ipsec-interfaces", "interface", "eth0"])
        self.cli_set(base_path + ["profile", "NHRPVPN", "authentication", "mode", "pre-shared-secret"])
        self.cli_set(base_path + ["profile", "NHRPVPN", "authentication", "pre-shared-secret", "secret"])
        self.cli_set(base_path + ["profile", "NHRPVPN", "bind", "tunnel", "tun100"])
        self.cli_set(base_path + ["profile", "NHRPVPN", "esp-group", "ESP-HUB"])
        self.cli_set(base_path + ["profile", "NHRPVPN", "ike-group", "IKE-HUB"])

        self.cli_commit()

        swanctl_lines = [
            'proposals = aes256-sha1-modp1024,aes128-sha1-modp1024',
            'version = 1',
            'rekey_time = 3600s',
            'esp_proposals = aes256-sha1-modp1024,3des-md5-modp1024',
            'local_ts = dynamic[gre]',
            'remote_ts = dynamic[gre]',
            'mode = transport',
            'secret = secret'
        ]

        tmp_swanctl_conf = read_file('/etc/swanctl/swanctl.conf')

        for line in swanctl_lines:
            self.assertIn(line, tmp_swanctl_conf)

        self.assertTrue(process_named_running('charon'))

if __name__ == '__main__':
    unittest.main(verbosity=2)
