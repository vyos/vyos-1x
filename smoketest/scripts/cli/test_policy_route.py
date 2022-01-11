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

from vyos.util import cmd

mark = '100'
table_mark_offset = 0x7fffffff
table_id = '101'

class TestPolicyRoute(VyOSUnitTestSHIM.TestCase):
    def setUp(self):
        self.cli_set(['interfaces', 'ethernet', 'eth0', 'address', '172.16.10.1/24'])
        self.cli_set(['protocols', 'static', 'table', '101', 'route', '0.0.0.0/0', 'interface', 'eth0'])

    def tearDown(self):
        self.cli_delete(['interfaces', 'ethernet', 'eth0'])
        self.cli_delete(['protocols', 'static'])
        self.cli_delete(['policy', 'route'])
        self.cli_delete(['policy', 'route6'])
        self.cli_commit()

    def test_pbr_mark(self):
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'source', 'address', '172.16.20.10'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'destination', 'address', '172.16.10.10'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'set', 'mark', mark])

        self.cli_set(['interfaces', 'ethernet', 'eth0', 'policy', 'route', 'smoketest'])

        self.cli_commit()

        mark_hex = "{0:#010x}".format(int(mark))

        nftables_search = [
            ['iifname "eth0"', 'jump VYOS_PBR_smoketest'],
            ['ip daddr 172.16.10.10', 'ip saddr 172.16.20.10', 'meta mark set ' + mark_hex],
        ]

        nftables_output = cmd('sudo nft list table ip mangle')

        for search in nftables_search:
            matched = False
            for line in nftables_output.split("\n"):
                if all(item in line for item in search):
                    matched = True
                    break
            self.assertTrue(matched)

    def test_pbr_table(self):
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'protocol', 'tcp_udp'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'destination', 'port', '8888'])
        self.cli_set(['policy', 'route', 'smoketest', 'rule', '1', 'set', 'table', table_id])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '1', 'protocol', 'tcp_udp'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '1', 'destination', 'port', '8888'])
        self.cli_set(['policy', 'route6', 'smoketest6', 'rule', '1', 'set', 'table', table_id])

        self.cli_set(['interfaces', 'ethernet', 'eth0', 'policy', 'route', 'smoketest'])
        self.cli_set(['interfaces', 'ethernet', 'eth0', 'policy', 'route6', 'smoketest6'])

        self.cli_commit()

        mark_hex = "{0:#010x}".format(table_mark_offset - int(table_id))

        # IPv4

        nftables_search = [
            ['iifname "eth0"', 'jump VYOS_PBR_smoketest'],
            ['meta l4proto { tcp, udp }', 'th dport { 8888 }', 'meta mark set ' + mark_hex]
        ]

        nftables_output = cmd('sudo nft list table ip mangle')

        for search in nftables_search:
            matched = False
            for line in nftables_output.split("\n"):
                if all(item in line for item in search):
                    matched = True
                    break
            self.assertTrue(matched)

        # IPv6

        nftables6_search = [
            ['iifname "eth0"', 'jump VYOS_PBR6_smoketest'],
            ['meta l4proto { tcp, udp }', 'th dport { 8888 }', 'meta mark set ' + mark_hex]
        ]

        nftables6_output = cmd('sudo nft list table ip6 mangle')

        for search in nftables6_search:
            matched = False
            for line in nftables6_output.split("\n"):
                if all(item in line for item in search):
                    matched = True
                    break
            self.assertTrue(matched)

        # IP rule fwmark -> table

        ip_rule_search = [
            ['fwmark ' + hex(table_mark_offset - int(table_id)), 'lookup ' + table_id]
        ]

        ip_rule_output = cmd('ip rule show')

        for search in ip_rule_search:
            matched = False
            for line in ip_rule_output.split("\n"):
                if all(item in line for item in search):
                    matched = True
                    break
            self.assertTrue(matched)


if __name__ == '__main__':
    unittest.main(verbosity=2)
