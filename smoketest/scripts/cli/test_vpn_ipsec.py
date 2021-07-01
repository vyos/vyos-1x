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

peer_ip = '203.0.113.45'
interface = 'eth1'
vif = '100'
esp_group = 'MyESPGroup'
ike_group = 'MyIKEGroup'
secret = 'MYSECRETKEY'

class TestVPNIPsec(VyOSUnitTestSHIM.TestCase):
    def setUp(self):
        self.cli_set(base_path + ['ipsec-interfaces', 'interface', f'{interface}.{vif}'])

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
        self.cli_delete(nhrp_path)
        self.cli_delete(tunnel_path)
        self.cli_delete(vti_path)
        self.cli_delete(ethernet_path)
        self.cli_commit()

        # Check for no longer running process
        self.assertFalse(process_named_running('charon'))

    def test_01_dhcp_fail_handling(self):
        # Interface for dhcp-interface
        self.cli_set(ethernet_path + [interface, 'vif', vif, 'address', 'dhcp']) # Use VLAN to avoid getting IP from qemu dhcp server

        # Site to site
        peer_base_path = base_path + ['site-to-site', 'peer', peer_ip]
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
        peer_base_path = base_path + ['site-to-site', 'peer', peer_ip]
        self.cli_set(peer_base_path + ['authentication', 'mode', 'pre-shared-secret'])
        self.cli_set(peer_base_path + ['authentication', 'pre-shared-secret', secret])
        self.cli_set(peer_base_path + ['ike-group', ike_group])
        self.cli_set(peer_base_path + ['default-esp-group', esp_group])
        self.cli_set(peer_base_path + ['local-address', '192.0.2.10'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'protocol', 'tcp'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'local', 'prefix', '172.16.10.0/24'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'local', 'prefix', '172.16.11.0/24'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'local', 'port', '443'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'remote', 'prefix', '172.17.10.0/24'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'remote', 'prefix', '172.17.11.0/24'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'remote', 'port', '443'])

        self.cli_commit()

        # Verify strongSwan configuration
        swanctl_conf = read_file(swanctl_file)
        swanctl_conf_lines = [
            f'version = 2',
            f'auth = psk',
            f'proposals = aes128-sha1-modp1024',
            f'esp_proposals = aes128-sha1-modp1024',
            f'local_addrs = 192.0.2.10 # dhcp:no',
            f'remote_addrs = {peer_ip}',
            f'mode = tunnel',
            f'local_ts = 172.16.10.0/24[tcp/443],172.16.11.0/24[tcp/443]',
            f'remote_ts = 172.17.10.0/24[tcp/443],172.17.11.0/24[tcp/443]'
        ]
        for line in swanctl_conf_lines:
            self.assertIn(line, swanctl_conf)

        swanctl_secrets_lines = [
            f'id-local = 192.0.2.10 # dhcp:no',
            f'id-remote = {peer_ip}',
            f'secret = "{secret}"'
        ]
        for line in swanctl_secrets_lines:
            self.assertIn(line, swanctl_conf)


    def test_03_site_to_site_vti(self):
        # VTI interface
        vti = 'vti10'
        self.cli_set(vti_path + [vti, 'address', '10.1.1.1/24'])

        self.cli_set(base_path + ['ike-group', ike_group, 'key-exchange', 'ikev2'])

        # Site to site
        peer_base_path = base_path + ['site-to-site', 'peer', peer_ip]
        self.cli_set(peer_base_path + ['authentication', 'mode', 'pre-shared-secret'])
        self.cli_set(peer_base_path + ['authentication', 'pre-shared-secret', secret])
        self.cli_set(peer_base_path + ['ike-group', ike_group])
        self.cli_set(peer_base_path + ['default-esp-group', esp_group])
        self.cli_set(peer_base_path + ['local-address', '192.0.2.10'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'local', 'prefix', '172.16.10.0/24'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'local', 'prefix', '172.16.11.0/24'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'remote', 'prefix', '172.17.10.0/24'])
        self.cli_set(peer_base_path + ['tunnel', '1', 'remote', 'prefix', '172.17.11.0/24'])
        self.cli_set(peer_base_path + ['vti', 'bind', vti])
        self.cli_set(peer_base_path + ['vti', 'esp-group', esp_group])

        self.cli_commit()

        swanctl_conf = read_file(swanctl_file)
        swanctl_conf_lines = [
            f'version = 2',
            f'auth = psk',
            f'proposals = aes128-sha1-modp1024',
            f'esp_proposals = aes128-sha1-modp1024',
            f'local_addrs = 192.0.2.10 # dhcp:no',
            f'remote_addrs = {peer_ip}',
            f'mode = tunnel',
            f'local_ts = 172.16.10.0/24,172.16.11.0/24',
            f'remote_ts = 172.17.10.0/24,172.17.11.0/24',
            f'if_id_in = {vti.lstrip("vti")}', # will be 10 for vti10
            f'if_id_out = {vti.lstrip("vti")}',
            f'updown = "/etc/ipsec.d/vti-up-down {vti} no"'
        ]
        for line in swanctl_conf_lines:
            self.assertIn(line, swanctl_conf)

        swanctl_secrets_lines = [
            f'id-local = 192.0.2.10 # dhcp:no',
            f'id-remote = {peer_ip}',
            f'secret = "{secret}"'
        ]
        for line in swanctl_secrets_lines:
            self.assertIn(line, swanctl_conf)


    def test_04_dmvpn(self):
        tunnel_if = 'tun100'
        nhrp_secret = 'secret'

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
        self.cli_set(base_path + ['esp-group', esp_group, 'compression', 'disable'])
        self.cli_set(base_path + ['esp-group', esp_group, 'lifetime', '1800'])
        self.cli_set(base_path + ['esp-group', esp_group, 'mode', 'transport'])
        self.cli_set(base_path + ['esp-group', esp_group, 'pfs', 'dh-group2'])
        self.cli_set(base_path + ['esp-group', esp_group, 'proposal', '2', 'encryption', 'aes256'])
        self.cli_set(base_path + ['esp-group', esp_group, 'proposal', '2', 'hash', 'sha1'])
        self.cli_set(base_path + ['esp-group', esp_group, 'proposal', '3', 'encryption', '3des'])
        self.cli_set(base_path + ['esp-group', esp_group, 'proposal', '3', 'hash', 'md5'])

        self.cli_set(base_path + ['ike-group', ike_group, 'ikev2-reauth', 'no'])
        self.cli_set(base_path + ['ike-group', ike_group, 'key-exchange', 'ikev1'])
        self.cli_set(base_path + ['ike-group', ike_group, 'lifetime', '3600'])
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
            f'rekey_time = 3600s',
            f'esp_proposals = aes128-sha1-modp1024,aes256-sha1-modp1024,3des-md5-modp1024',
            f'local_ts = dynamic[gre]',
            f'remote_ts = dynamic[gre]',
            f'mode = transport',
            f'secret = {nhrp_secret}'
        ]
        for line in swanctl_lines:
            self.assertIn(line, swanctl_conf)


if __name__ == '__main__':
    unittest.main(verbosity=2)
