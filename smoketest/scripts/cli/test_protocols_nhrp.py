#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.utils.process import process_named_running

tunnel_path = ['interfaces', 'tunnel']
nhrp_path = ['protocols', 'nhrp']
vpn_path = ['vpn', 'ipsec']
PROCESS_NAME = 'nhrpd'

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

    def test_01_nhrp_config(self):
        tunnel_if = "tun100"
        tunnel_ip = '172.16.253.134/32'
        tunnel_source = "192.0.2.134"
        tunnel_encapsulation = "gre"
        esp_group = "ESP-HUB"
        ike_group = "IKE-HUB"
        nhrp_secret = "vyos123"
        nhrp_profile = "NHRPVPN"
        nhrp_holdtime = '300'
        nhs_tunnelip = '172.16.253.1'
        nhs_nbmaip = '192.0.2.1'
        map_tunnelip = '172.16.253.135'
        map_nbmaip = "192.0.2.135"
        nhrp_networkid = '1'
        ipsec_secret = "secret"
        multicat_log_group = '2'
        redirect_log_group = '1'
        # Tunnel
        self.cli_set(tunnel_path + [tunnel_if, "address", tunnel_ip])
        self.cli_set(tunnel_path + [tunnel_if, "encapsulation", tunnel_encapsulation])
        self.cli_set(tunnel_path + [tunnel_if, "source-address", tunnel_source])
        self.cli_set(tunnel_path + [tunnel_if, "enable-multicast"])
        self.cli_set(tunnel_path + [tunnel_if, "parameters", "ip", "key", "1"])

        # NHRP
        self.cli_set(nhrp_path + ["tunnel", tunnel_if, "authentication", nhrp_secret])
        self.cli_set(nhrp_path + ["tunnel", tunnel_if, "holdtime", nhrp_holdtime])
        self.cli_set(nhrp_path + ["tunnel", tunnel_if, "multicast", nhs_tunnelip])
        self.cli_set(nhrp_path + ["tunnel", tunnel_if, "redirect"])
        self.cli_set(nhrp_path + ["tunnel", tunnel_if, "shortcut"])
        self.cli_set(nhrp_path + ["tunnel", tunnel_if, "registration-no-unique"])
        self.cli_set(nhrp_path + ["tunnel", tunnel_if, "network-id", nhrp_networkid])
        self.cli_set(nhrp_path + ["tunnel", tunnel_if, "nhs", "tunnel-ip", nhs_tunnelip, "nbma", nhs_nbmaip])
        self.cli_set(nhrp_path + ["tunnel", tunnel_if, "map", "tunnel-ip", map_tunnelip, "nbma", map_nbmaip])

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

        frrconfig = self.getFRRconfig(f'interface {tunnel_if}', endsection='^exit')
        self.assertIn(f'interface {tunnel_if}', frrconfig)
        self.assertIn(f' ip nhrp authentication {nhrp_secret}', frrconfig)
        self.assertIn(f' ip nhrp holdtime {nhrp_holdtime}', frrconfig)
        self.assertIn(f' ip nhrp map multicast {nhs_tunnelip}', frrconfig)
        self.assertIn(f' ip nhrp redirect', frrconfig)
        self.assertIn(f' ip nhrp registration no-unique', frrconfig)
        self.assertIn(f' ip nhrp shortcut', frrconfig)
        self.assertIn(f' ip nhrp network-id {nhrp_networkid}', frrconfig)
        self.assertIn(f' ip nhrp nhs {nhs_tunnelip} nbma {nhs_nbmaip}', frrconfig)
        self.assertIn(f' ip nhrp map {map_tunnelip} {map_nbmaip}', frrconfig)
        self.assertIn(f' tunnel protection vici profile dmvpn-{nhrp_profile}-{tunnel_if}-child',
                      frrconfig)

        nftables_search_multicast = [
            ['chain VYOS_NHRP_MULTICAST_OUTPUT'],
            ['type filter hook output priority filter + 10; policy accept;'],
            [f'oifname "{tunnel_if}"', 'ip daddr 224.0.0.0/24', 'counter', f'log group {multicat_log_group}'],
            [f'oifname "{tunnel_if}"', 'ip daddr 224.0.0.0/24', 'counter', 'drop'],
            ['chain VYOS_NHRP_MULTICAST_FORWARD'],
            ['type filter hook output priority filter + 10; policy accept;'],
            [f'oifname "{tunnel_if}"', 'ip daddr 224.0.0.0/4', 'counter', f'log group {multicat_log_group}'],
            [f'oifname "{tunnel_if}"', 'ip daddr 224.0.0.0/4', 'counter', 'drop']
        ]

        nftables_search_redirect = [
            ['chain VYOS_NHRP_REDIRECT_FORWARD'],
            ['type filter hook forward priority filter + 10; policy accept;'],
            [f'iifname "{tunnel_if}" oifname "{tunnel_if}"', 'meter loglimit-0 size 65535 { ip daddr & 255.255.255.0 . ip saddr & 255.255.255.0 timeout 1m limit rate 4/minute burst 1 packets }', 'counter', f'log group {redirect_log_group}']
        ]
        self.verify_nftables(nftables_search_multicast, 'ip vyos_nhrp_multicast')
        self.verify_nftables(nftables_search_redirect, 'ip vyos_nhrp_redirect')

        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    unittest.main(verbosity=2)
