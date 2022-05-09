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
    @classmethod
    def setUpClass(cls):
        super(TestFirewall, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, ['firewall'])

        cls.cli_set(cls, ['interfaces', 'ethernet', 'eth0', 'address', '172.16.10.1/24'])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['interfaces', 'ethernet', 'eth0', 'address', '172.16.10.1/24'])
        super(TestFirewall, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(['interfaces', 'ethernet', 'eth0', 'firewall'])
        self.cli_delete(['firewall'])
        self.cli_commit()

    def test_groups(self):
        self.cli_set(['firewall', 'group', 'mac-group', 'smoketest_mac', 'mac-address', '00:01:02:03:04:05'])
        self.cli_set(['firewall', 'group', 'network-group', 'smoketest_network', 'network', '172.16.99.0/24'])
        self.cli_set(['firewall', 'group', 'port-group', 'smoketest_port', 'port', '53'])
        self.cli_set(['firewall', 'group', 'port-group', 'smoketest_port', 'port', '123'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'source', 'group', 'network-group', 'smoketest_network'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'destination', 'address', '172.16.10.10'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'destination', 'group', 'port-group', 'smoketest_port'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'protocol', 'tcp_udp'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'action', 'accept'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'source', 'group', 'mac-group', 'smoketest_mac'])

        self.cli_set(['interfaces', 'ethernet', 'eth0', 'firewall', 'in', 'name', 'smoketest'])

        self.cli_commit()

        nftables_search = [
            ['iifname "eth0"', 'jump NAME_smoketest'],
            ['ip saddr { 172.16.99.0/24 }', 'ip daddr 172.16.10.10', 'th dport { 53, 123 }', 'return'],
            ['ether saddr { 00:01:02:03:04:05 }', 'return']
        ]

        nftables_output = cmd('sudo nft list table ip filter')

        for search in nftables_search:
            matched = False
            for line in nftables_output.split("\n"):
                if all(item in line for item in search):
                    matched = True
                    break
            self.assertTrue(matched, msg=search)

    def test_basic_rules(self):
        self.cli_set(['firewall', 'name', 'smoketest', 'default-action', 'drop'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'source', 'address', '172.16.20.10'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'destination', 'address', '172.16.10.10'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'action', 'reject'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'destination', 'port', '8888'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'tcp', 'flags', 'syn'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'tcp', 'flags', 'not', 'ack'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '3', 'action', 'accept'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '3', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '3', 'destination', 'port', '22'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '3', 'limit', 'rate', '5/minute'])

        self.cli_set(['interfaces', 'ethernet', 'eth0', 'firewall', 'in', 'name', 'smoketest'])

        self.cli_commit()

        nftables_search = [
            ['iifname "eth0"', 'jump NAME_smoketest'],
            ['saddr 172.16.20.10', 'daddr 172.16.10.10', 'return'],
            ['tcp flags & (syn | ack) == syn', 'tcp dport { 8888 }', 'reject'],
            ['tcp dport { 22 }', 'limit rate 5/minute', 'return'],
            ['smoketest default-action', 'drop']
        ]

        nftables_output = cmd('sudo nft list table ip filter')

        for search in nftables_search:
            matched = False
            for line in nftables_output.split("\n"):
                if all(item in line for item in search):
                    matched = True
                    break
            self.assertTrue(matched, msg=search)

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
            ['iifname "eth0"', 'jump NAME6_v6-smoketest'],
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
            self.assertTrue(matched, msg=search)

    def test_state_policy(self):
        self.cli_set(['firewall', 'state-policy', 'established', 'action', 'accept'])
        self.cli_set(['firewall', 'state-policy', 'related', 'action', 'accept'])
        self.cli_set(['firewall', 'state-policy', 'invalid', 'action', 'drop'])

        self.cli_commit()

        chains = {
            'ip filter': ['VYOS_FW_FORWARD', 'VYOS_FW_OUTPUT', 'VYOS_FW_LOCAL'],
            'ip6 filter': ['VYOS_FW6_FORWARD', 'VYOS_FW6_OUTPUT', 'VYOS_FW6_LOCAL']
        }

        for table in ['ip filter', 'ip6 filter']:
            for chain in chains[table]:
                nftables_output = cmd(f'sudo nft list chain {table} {chain}')
                self.assertTrue('jump VYOS_STATE_POLICY' in nftables_output)

    def test_state_and_status_rules(self):
        self.cli_set(['firewall', 'name', 'smoketest', 'default-action', 'drop'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'state', 'established', 'enable'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'state', 'related', 'enable'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'action', 'reject'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'state', 'invalid', 'enable'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '3', 'action', 'accept'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '3', 'state', 'new', 'enable'])

        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '3', 'connection-status', 'nat', 'destination'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '4', 'action', 'accept'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '4', 'state', 'new', 'enable'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '4', 'state', 'established', 'enable'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '4', 'connection-status', 'nat', 'source'])

        self.cli_set(['interfaces', 'ethernet', 'eth0', 'firewall', 'in', 'name', 'smoketest'])

        self.cli_commit()

        nftables_search = [
            ['iifname "eth0"', 'jump NAME_smoketest'],
            ['ct state { established, related }', 'return'],
            ['ct state { invalid }', 'reject'],
            ['ct state { new }', 'ct status { dnat }', 'return'],
            ['ct state { established, new }', 'ct status { snat }', 'return'],
            ['smoketest default-action', 'drop']
        ]

        nftables_output = cmd('sudo nft list table ip filter')

        for search in nftables_search:
            matched = False
            for line in nftables_output.split("\n"):
                if all(item in line for item in search):
                    matched = True
                    break
            self.assertTrue(matched, msg=search)

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
