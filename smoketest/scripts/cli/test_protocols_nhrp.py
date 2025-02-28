#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.firewall import find_nftables_rule
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file

tunnel_path = ['interfaces', 'tunnel']
nhrp_path = ['protocols', 'nhrp']
vpn_path = ['vpn', 'ipsec']

class TestProtocolsNHRP(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProtocolsNHRP, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, nhrp_path)
        cls.cli_delete(cls, tunnel_path)

    def tearDown(self):
        self.cli_delete(nhrp_path)
        self.cli_delete(tunnel_path)
        self.cli_commit()

    def test_config(self):
        tunnel_if = "tun100"
        tunnel_source = "192.0.2.1"
        tunnel_encapsulation = "gre"
        esp_group = "ESP-HUB"
        ike_group = "IKE-HUB"
        nhrp_secret = "vyos123"
        nhrp_profile = "NHRPVPN"
        ipsec_secret = "secret"

        # Tunnel
        self.cli_set(tunnel_path + [tunnel_if, "address", "172.16.253.134/29"])
        self.cli_set(tunnel_path + [tunnel_if, "encapsulation", tunnel_encapsulation])
        self.cli_set(tunnel_path + [tunnel_if, "source-address", tunnel_source])
        self.cli_set(tunnel_path + [tunnel_if, "enable-multicast"])
        self.cli_set(tunnel_path + [tunnel_if, "parameters", "ip", "key", "1"])

        # NHRP
        self.cli_set(nhrp_path + ["tunnel", tunnel_if, "cisco-authentication", nhrp_secret])
        self.cli_set(nhrp_path + ["tunnel", tunnel_if, "holding-time", "300"])
        self.cli_set(nhrp_path + ["tunnel", tunnel_if, "multicast", "dynamic"])
        self.cli_set(nhrp_path + ["tunnel", tunnel_if, "redirect"])
        self.cli_set(nhrp_path + ["tunnel", tunnel_if, "shortcut"])

        # IKE/ESP Groups
        self.cli_set(vpn_path + ["esp-group", esp_group, "lifetime", "1800"])
        self.cli_set(vpn_path + ["esp-group", esp_group, "mode", "transport"])
        self.cli_set(vpn_path + ["esp-group", esp_group, "pfs", "dh-group2"])
        self.cli_set(vpn_path + ["esp-group", esp_group, "proposal", "1", "encryption", "aes256"])
        self.cli_set(vpn_path + ["esp-group", esp_group, "proposal", "1", "hash", "sha1"])
        self.cli_set(vpn_path + ["esp-group", esp_group, "proposal", "2", "encryption", "3des"])
        self.cli_set(vpn_path + ["esp-group", esp_group, "proposal", "2", "hash", "md5"])

        self.cli_set(vpn_path + ["ike-group", ike_group, "key-exchange", "ikev1"])
        self.cli_set(vpn_path + ["ike-group", ike_group, "lifetime", "3600"])
        self.cli_set(vpn_path + ["ike-group", ike_group, "proposal", "1", "dh-group", "2"])
        self.cli_set(vpn_path + ["ike-group", ike_group, "proposal", "1", "encryption", "aes256"])
        self.cli_set(vpn_path + ["ike-group", ike_group, "proposal", "1", "hash", "sha1"])
        self.cli_set(vpn_path + ["ike-group", ike_group, "proposal", "2", "dh-group", "2"])
        self.cli_set(vpn_path + ["ike-group", ike_group, "proposal", "2", "encryption", "aes128"])
        self.cli_set(vpn_path + ["ike-group", ike_group, "proposal", "2", "hash", "sha1"])

        # Profile - Not doing full DMVPN checks here, just want to verify the profile name in the output
        self.cli_set(vpn_path + ["interface", "eth0"])
        self.cli_set(vpn_path + ["profile", nhrp_profile, "authentication", "mode", "pre-shared-secret"])
        self.cli_set(vpn_path + ["profile", nhrp_profile, "authentication", "pre-shared-secret", ipsec_secret])
        self.cli_set(vpn_path + ["profile", nhrp_profile, "bind", "tunnel", tunnel_if])
        self.cli_set(vpn_path + ["profile", nhrp_profile, "esp-group", esp_group])
        self.cli_set(vpn_path + ["profile", nhrp_profile, "ike-group", ike_group])

        self.cli_commit()

        opennhrp_lines = [
            f'interface {tunnel_if} #hub {nhrp_profile}',
            f'cisco-authentication {nhrp_secret}',
            f'holding-time 300',
            f'shortcut',
            f'multicast dynamic',
            f'redirect'
        ]

        tmp_opennhrp_conf = read_file('/run/opennhrp/opennhrp.conf')

        for line in opennhrp_lines:
            self.assertIn(line, tmp_opennhrp_conf)

        firewall_matches = [
            f'ip protocol {tunnel_encapsulation}',
            f'ip saddr {tunnel_source}',
            f'ip daddr 224.0.0.0/4',
            f'comment "VYOS_NHRP_{tunnel_if}"'
        ]

        self.assertTrue(find_nftables_rule('ip vyos_nhrp_filter', 'VYOS_NHRP_OUTPUT', firewall_matches) is not None)
        self.assertTrue(process_named_running('opennhrp'))

if __name__ == '__main__':
    unittest.main(verbosity=2)
