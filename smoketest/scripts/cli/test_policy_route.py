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

import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.utils.process import cmd

mark = '100'
conn_mark = '555'
conn_mark_set = '111'
table_mark_offset = 0x7fffffff
table_id = '101'
interface = 'eth0'
interface_wc = 'ppp*'
interface_ip = '172.16.10.1/24'

class TestPolicyRoute(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestPolicyRoute, cls).setUpClass()
        # Clear out current configuration to allow running this test on a live system
        cls.cli_delete(cls, ['policy', 'route'])
        cls.cli_delete(cls, ['policy', 'route6'])

        cls.cli_set(cls, ['interfaces', 'ethernet', interface, 'address', interface_ip])
        cls.cli_set(cls, ['protocols', 'static', 'table', table_id, 'route', '0.0.0.0/0', 'interface', interface])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['interfaces', 'ethernet', interface, 'address', interface_ip])
        cls.cli_delete(cls, ['protocols', 'static', 'table', table_id])

        super(TestPolicyRoute, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(['policy', 'route'])
        self.cli_delete(['policy', 'route6'])
        self.cli_commit()

        # Verify nftables cleanup
        nftables_search = [
            ['set N_smoketest_network'],
            ['set N_smoketest_network1'],
            ['chain VYOS_PBR_smoketest']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_mangle', inverse=True)

        # Verify ip rule cleanup
        ip_rule_search = [
            ['fwmark ' + hex(table_mark_offset - int(table_id)), 'lookup ' + table_id]
        ]

        self.verify_rules(ip_rule_search, inverse=True)

    def verify_rules(self, rules_search, inverse=False):
        rule_output = cmd('ip rule show')

        for search in rules_search:
            matched = False
            for line in rule_output.split("\n"):
                if all(item in line for item in search):
                    matched = True
                    break
            self.assertTrue(not matched if inverse else matched, msg=search)

    def test_pbr_group(self):
        self.cli_set(['firewall', 'group', 'network-group', 'smoketest_network', 'network', '172.16.99.0/24'])
        self.cli_set(['firewall', 'group', 'network-group', 'smoketest_network1', 'network', '172.16.101.0/24'])
        self.cli_set(['firewall', 'group', 'network-group', 'smoketest_network1', 'include', 'smoketest_network'])

        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'source', 'group', 'network-group', 'smoketest_network'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'destination', 'group', 'network-group', 'smoketest_network1'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'set', 'mark', mark])
        self.cli_set(['policy', 'route', 'smoketest', 'interface', interface])

        self.cli_commit()

        nftables_search = [
            [f'iifname "{interface}"','jump VYOS_PBR_UD_smoketest'],
            ['ip daddr @N_smoketest_network1', 'ip saddr @N_smoketest_network'],
        ]

        self.verify_nftables(nftables_search, 'ip vyos_mangle')

        self.cli_delete(['firewall'])

    def test_pbr_mark(self):
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'source', 'address', '172.16.20.10'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'destination', 'address', '172.16.10.10'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'set', 'mark', mark])
        self.cli_set(['policy', 'route', 'smoketest', 'interface', interface])

        self.cli_commit()

        mark_hex = "{0:#010x}".format(int(mark))

        nftables_search = [
            [f'iifname "{interface}"','jump VYOS_PBR_UD_smoketest'],
            ['ip daddr 172.16.10.10', 'ip saddr 172.16.20.10', 'meta mark set ' + mark_hex],
        ]

        self.verify_nftables(nftables_search, 'ip vyos_mangle')

    def test_pbr_mark_connection(self):
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'source', 'address', '172.16.20.10'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'destination', 'address', '172.16.10.10'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'connection-mark', conn_mark])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'set', 'connection-mark', conn_mark_set])
        self.cli_set(['policy', 'route', 'smoketest', 'interface', interface])

        self.cli_commit()

        mark_hex = "{0:#010x}".format(int(conn_mark))
        mark_hex_set = "{0:#010x}".format(int(conn_mark_set))

        nftables_search = [
            [f'iifname "{interface}"','jump VYOS_PBR_UD_smoketest'],
            ['ip daddr 172.16.10.10', 'ip saddr 172.16.20.10', 'ct mark ' + mark_hex, 'ct mark set ' + mark_hex_set],
        ]

        self.verify_nftables(nftables_search, 'ip vyos_mangle')

    def test_pbr_table(self):
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'protocol', 'tcp'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'destination', 'port', '8888'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'tcp', 'flags', 'syn'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'tcp', 'flags', 'not', 'ack'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'set', 'table', table_id])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '1', 'protocol', 'tcp_udp'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '1', 'destination', 'port', '8888'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '1', 'set', 'table', table_id])

        self.cli_set(['policy', 'route', 'smoketest', 'interface', interface])
        self.cli_set(['policy', 'route6', 'smoketest6', 'interface', interface])

        self.cli_commit()

        mark_hex = "{0:#010x}".format(table_mark_offset - int(table_id))

        # IPv4

        nftables_search = [
            [f'iifname "{interface}"', 'jump VYOS_PBR_UD_smoketest'],
            ['tcp flags syn / syn,ack', 'tcp dport 8888', 'meta mark set ' + mark_hex]
        ]

        self.verify_nftables(nftables_search, 'ip vyos_mangle')

        # IPv6

        nftables6_search = [
            [f'iifname "{interface}"', 'jump VYOS_PBR6_UD_smoketest'],
            ['meta l4proto { tcp, udp }', 'th dport 8888', 'meta mark set ' + mark_hex]
        ]

        self.verify_nftables(nftables6_search, 'ip6 vyos_mangle')

        # IP rule fwmark -> table

        ip_rule_search = [
            ['fwmark ' + hex(table_mark_offset - int(table_id)), 'lookup ' + table_id]
        ]

        self.verify_rules(ip_rule_search)


    def test_pbr_matching_criteria(self):
        self.cli_set(['policy', 'route', 'smoketest', 'default-log'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'protocol', 'udp'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'action', 'drop'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'mark', '2020'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '2', 'protocol', 'tcp'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '2', 'tcp', 'flags', 'syn'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '2', 'tcp', 'flags', 'not', 'ack'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '2', 'mark', '2-3000'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '2', 'set', 'table', table_id])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '3', 'source', 'address', '198.51.100.0/24'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '3', 'protocol', 'tcp'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '3', 'destination', 'port', '22'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '3', 'state', 'new'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '3', 'ttl', 'gt', '2'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '3', 'mark', '!456'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '3', 'set', 'table', table_id])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '4', 'protocol', 'icmp'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '4', 'icmp', 'type-name', 'echo-request'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '4', 'packet-length', '128'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '4', 'packet-length', '1024-2048'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '4', 'packet-type', 'other'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '4', 'log'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '4', 'set', 'table', table_id])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '5', 'dscp', '41'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '5', 'dscp', '57-59'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '5', 'mark', '!456-500'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '5', 'set', 'table', table_id])

        self.cli_set(['policy', 'route6', 'smoketest6', 'default-log'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '1', 'protocol', 'udp'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '1', 'action', 'drop'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '2', 'protocol', 'tcp'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '2', 'tcp', 'flags', 'syn'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '2', 'tcp', 'flags', 'not', 'ack'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '2', 'set', 'table', table_id])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '3', 'source', 'address', '2001:db8::0/64'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '3', 'protocol', 'tcp'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '3', 'destination', 'port', '22'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '3', 'state', 'new'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '3', 'hop-limit', 'gt', '2'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '3', 'set', 'table', table_id])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '4', 'protocol', 'icmpv6'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '4', 'icmpv6', 'type', 'echo-request'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '4', 'packet-length-exclude', '128'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '4', 'packet-length-exclude', '1024-2048'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '4', 'packet-type', 'multicast'])

        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '4', 'log'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '4', 'set', 'table', table_id])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '5', 'dscp-exclude', '61'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '5', 'dscp-exclude', '14-19'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '5', 'set', 'table', table_id])

        self.cli_set(['policy', 'route', 'smoketest', 'interface', interface])
        self.cli_set(['policy', 'route', 'smoketest', 'interface', interface_wc])
        self.cli_set(['policy', 'route6', 'smoketest6', 'interface', interface_wc])

        self.cli_commit()

        mark_hex = "{0:#010x}".format(table_mark_offset - int(table_id))

        # IPv4
        nftables_search = [
            ['iifname { "' + interface + '", "' + interface_wc + '" }', 'jump VYOS_PBR_UD_smoketest'],
            ['meta l4proto udp', 'meta mark 0x000007e4', 'drop'],
            ['tcp flags syn / syn,ack', 'meta mark 0x00000002-0x00000bb8', 'meta mark set ' + mark_hex],
            ['ct state new', 'tcp dport 22', 'ip saddr 198.51.100.0/24', 'ip ttl > 2', 'meta mark != 0x000001c8', 'meta mark set ' + mark_hex],
            ['log prefix "[ipv4-route-smoketest-4-A]"', 'icmp type echo-request', 'ip length { 128, 1024-2048 }', 'meta pkttype other', 'meta mark set ' + mark_hex],
            ['ip dscp { 0x29, 0x39-0x3b }', 'meta mark != 0x000001c8-0x000001f4', 'meta mark set ' + mark_hex],
            ['log prefix "[ipv4-smoketest-default]"']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_mangle')

        # IPv6
        nftables6_search = [
            [f'iifname "{interface_wc}"', 'jump VYOS_PBR6_UD_smoketest'],
            ['meta l4proto udp', 'drop'],
            ['tcp flags syn / syn,ack', 'meta mark set ' + mark_hex],
            ['ct state new', 'tcp dport 22', 'ip6 saddr 2001:db8::/64', 'ip6 hoplimit > 2', 'meta mark set ' + mark_hex],
            ['log prefix "[ipv6-route6-smoketest6-4-A]"', 'icmpv6 type echo-request', 'ip6 length != { 128, 1024-2048 }', 'meta pkttype multicast', 'meta mark set ' + mark_hex],
            ['ip6 dscp != { 0x0e-0x13, 0x3d }', 'meta mark set ' + mark_hex],
            ['log prefix "[ipv6-smoketest6-default]"']
        ]

        self.verify_nftables(nftables6_search, 'ip6 vyos_mangle')

if __name__ == '__main__':
    unittest.main(verbosity=2)
