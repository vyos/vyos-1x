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

from glob import glob

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.util import cmd

sysfs_config = {
    'all_ping': {'sysfs': '/proc/sys/net/ipv4/icmp_echo_ignore_all', 'default': '0', 'test_value': 'disable'},
    'broadcast_ping': {'sysfs': '/proc/sys/net/ipv4/icmp_echo_ignore_broadcasts', 'default': '1', 'test_value': 'enable'},
    'ip_src_route': {'sysfs': '/proc/sys/net/ipv4/conf/*/accept_source_route', 'default': '0', 'test_value': 'enable'},
    'ipv6_receive_redirects': {'sysfs': '/proc/sys/net/ipv6/conf/*/accept_redirects', 'default': '0', 'test_value': 'enable'},
    'ipv6_src_route': {'sysfs': '/proc/sys/net/ipv6/conf/*/accept_source_route', 'default': '-1', 'test_value': 'enable'},
    'log_martians': {'sysfs': '/proc/sys/net/ipv4/conf/all/log_martians', 'default': '1', 'test_value': 'disable'},
    'receive_redirects': {'sysfs': '/proc/sys/net/ipv4/conf/*/accept_redirects', 'default': '0', 'test_value': 'enable'},
    'send_redirects': {'sysfs': '/proc/sys/net/ipv4/conf/*/send_redirects', 'default': '1', 'test_value': 'disable'},
    'syn_cookies': {'sysfs': '/proc/sys/net/ipv4/tcp_syncookies', 'default': '1', 'test_value': 'disable'},
    'twa_hazards_protection': {'sysfs': '/proc/sys/net/ipv4/tcp_rfc1337', 'default': '0', 'test_value': 'enable'}
}

class TestFirewall(VyOSUnitTestSHIM.TestCase):
    def setUp(self):
        self.cli_set(['interfaces', 'ethernet', 'eth0', 'address', '172.16.10.1/24'])

    def tearDown(self):
        self.cli_delete(['interfaces', 'ethernet', 'eth0'])
        self.cli_commit()
        self.cli_delete(['firewall'])
        self.cli_commit()

    def test_groups(self):
        self.cli_set(['firewall', 'group', 'network-group', 'smoketest_network', 'network', '172.16.99.0/24'])
        self.cli_set(['firewall', 'group', 'port-group', 'smoketest_port', 'port', '53'])
        self.cli_set(['firewall', 'group', 'port-group', 'smoketest_port', 'port', '123'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'source', 'group', 'network-group', 'smoketest_network'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'destination', 'address', '172.16.10.10'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'destination', 'group', 'port-group', 'smoketest_port'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'protocol', 'tcp'])

        self.cli_set(['interfaces', 'ethernet', 'eth0', 'firewall', 'in', 'name', 'smoketest'])

        self.cli_commit()

        nftables_search = [
            ['iifname "eth0"', 'jump smoketest'],
            ['ip saddr { 172.16.99.0/24 }', 'ip daddr 172.16.10.10', 'tcp dport { 53, 123 }', 'return'],
        ]

        nftables_output = cmd('sudo nft list table ip filter')

        for search in nftables_search:
            matched = False
            for line in nftables_output.split("\n"):
                if all(item in line for item in search):
                    matched = True
                    break
            self.assertTrue(matched)

    def test_basic_rules(self):
        self.cli_set(['firewall', 'name', 'smoketest', 'default-action', 'drop'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'source', 'address', '172.16.20.10'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'destination', 'address', '172.16.10.10'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'action', 'reject'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'protocol', 'tcp_udp'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'destination', 'port', '8888'])

        self.cli_set(['interfaces', 'ethernet', 'eth0', 'firewall', 'in', 'name', 'smoketest'])

        self.cli_commit()

        nftables_search = [
            ['iifname "eth0"', 'jump smoketest'],
            ['saddr 172.16.20.10', 'daddr 172.16.10.10', 'return'],
            ['meta l4proto { tcp, udp }', 'th dport { 8888 }', 'reject'],
            ['smoketest default-action', 'drop']
        ]

        nftables_output = cmd('sudo nft list table ip filter')

        for search in nftables_search:
            matched = False
            for line in nftables_output.split("\n"):
                if all(item in line for item in search):
                    matched = True
                    break
            self.assertTrue(matched)

    def test_basic_rules_ipv6(self):
        self.cli_set(['firewall', 'ipv6-name', 'v6-smoketest', 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv6-name', 'v6-smoketest', 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv6-name', 'v6-smoketest', 'rule', '1', 'source', 'address', '2002::1'])
        self.cli_set(['firewall', 'ipv6-name', 'v6-smoketest', 'rule', '1', 'destination', 'address', '2002::1:1'])
        self.cli_set(['firewall', 'ipv6-name', 'v6-smoketest', 'rule', '2', 'action', 'reject'])
        self.cli_set(['firewall', 'ipv6-name', 'v6-smoketest', 'rule', '2', 'protocol', 'tcp_udp'])
        self.cli_set(['firewall', 'ipv6-name', 'v6-smoketest', 'rule', '2', 'destination', 'port', '8888'])

        self.cli_set(['interfaces', 'ethernet', 'eth0', 'firewall', 'in', 'ipv6-name', 'v6-smoketest'])

        self.cli_commit()

        nftables_search = [
            ['iifname "eth0"', 'jump v6-smoketest'],
            ['saddr 2002::1', 'daddr 2002::1:1', 'return'],
            ['meta l4proto { tcp, udp }', 'th dport { 8888 }', 'reject'],
            ['smoketest default-action', 'drop']
        ]

        nftables_output = cmd('sudo nft list table ip6 filter')

        for search in nftables_search:
            matched = False
            for line in nftables_output.split("\n"):
                if all(item in line for item in search):
                    matched = True
                    break
            self.assertTrue(matched)

    def test_sysfs(self):
        for name, conf in sysfs_config.items():
            paths = glob(conf['sysfs'])
            for path in paths:
                with open(path, 'r') as f:
                    self.assertEqual(f.read().strip(), conf['default'], msg=path)

            self.cli_set(['firewall', name.replace("_", "-"), conf['test_value']])

        self.cli_commit()

        for name, conf in sysfs_config.items():
            paths = glob(conf['sysfs'])
            for path in paths:
                with open(path, 'r') as f:
                    self.assertNotEqual(f.read().strip(), conf['default'], msg=path)

if __name__ == '__main__':
    unittest.main(verbosity=2)
