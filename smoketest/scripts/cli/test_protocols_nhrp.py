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

import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.firewall import find_nftables_rule
from vyos.util import call, process_named_running, read_file

tunnel_path = ['interfaces', 'tunnel']
nhrp_path = ['protocols', 'nhrp']
vpn_path = ['vpn', 'ipsec']

class TestProtocolsNHRP(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        self.cli_delete(nhrp_path)
        self.cli_delete(tunnel_path)
        self.cli_commit()

    def test_config(self):
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
        self.cli_set(vpn_path + ["esp-group", "ESP-HUB", "compression", "disable"])
        self.cli_set(vpn_path + ["esp-group", "ESP-HUB", "lifetime", "1800"])
        self.cli_set(vpn_path + ["esp-group", "ESP-HUB", "mode", "transport"])
        self.cli_set(vpn_path + ["esp-group", "ESP-HUB", "pfs", "dh-group2"])
        self.cli_set(vpn_path + ["esp-group", "ESP-HUB", "proposal", "1", "encryption", "aes256"])
        self.cli_set(vpn_path + ["esp-group", "ESP-HUB", "proposal", "1", "hash", "sha1"])
        self.cli_set(vpn_path + ["esp-group", "ESP-HUB", "proposal", "2", "encryption", "3des"])
        self.cli_set(vpn_path + ["esp-group", "ESP-HUB", "proposal", "2", "hash", "md5"])
        self.cli_set(vpn_path + ["ike-group", "IKE-HUB", "ikev2-reauth", "no"])
        self.cli_set(vpn_path + ["ike-group", "IKE-HUB", "key-exchange", "ikev1"])
        self.cli_set(vpn_path + ["ike-group", "IKE-HUB", "lifetime", "3600"])
        self.cli_set(vpn_path + ["ike-group", "IKE-HUB", "proposal", "1", "dh-group", "2"])
        self.cli_set(vpn_path + ["ike-group", "IKE-HUB", "proposal", "1", "encryption", "aes256"])
        self.cli_set(vpn_path + ["ike-group", "IKE-HUB", "proposal", "1", "hash", "sha1"])
        self.cli_set(vpn_path + ["ike-group", "IKE-HUB", "proposal", "2", "dh-group", "2"])
        self.cli_set(vpn_path + ["ike-group", "IKE-HUB", "proposal", "2", "encryption", "aes128"])
        self.cli_set(vpn_path + ["ike-group", "IKE-HUB", "proposal", "2", "hash", "sha1"])

        # Profile - Not doing full DMVPN checks here, just want to verify the profile name in the output
        self.cli_set(vpn_path + ["interface", "eth0"])
        self.cli_set(vpn_path + ["profile", "NHRPVPN", "authentication", "mode", "pre-shared-secret"])
        self.cli_set(vpn_path + ["profile", "NHRPVPN", "authentication", "pre-shared-secret", "secret"])
        self.cli_set(vpn_path + ["profile", "NHRPVPN", "bind", "tunnel", "tun100"])
        self.cli_set(vpn_path + ["profile", "NHRPVPN", "esp-group", "ESP-HUB"])
        self.cli_set(vpn_path + ["profile", "NHRPVPN", "ike-group", "IKE-HUB"])

        self.cli_commit()

        opennhrp_lines = [
            'interface tun100 #hub NHRPVPN',
            'cisco-authentication secret',
            'holding-time 300',
            'shortcut',
            'multicast dynamic',
            'redirect'
        ]

        tmp_opennhrp_conf = read_file('/run/opennhrp/opennhrp.conf')

        for line in opennhrp_lines:
            self.assertIn(line, tmp_opennhrp_conf)

        firewall_matches = [
            'ip protocol gre',
            'ip saddr 192.0.2.1',
            'ip daddr 224.0.0.0/4',
            'comment "VYOS_NHRP_tun100"'
        ]

        self.assertTrue(find_nftables_rule('ip vyos_filter', 'VYOS_FW_OUTPUT', firewall_matches) is not None)
        self.assertTrue(process_named_running('opennhrp'))

if __name__ == '__main__':
    unittest.main(verbosity=2)
