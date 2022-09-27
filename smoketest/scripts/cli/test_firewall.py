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

from vyos.configsession import ConfigSessionError
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

    @classmethod
    def tearDownClass(cls):
        super(TestFirewall, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(['firewall'])
        self.cli_commit()

        # Verify chains/sets are cleaned up from nftables
        nftables_search = [
            ['set M_smoketest_mac'],
            ['set N_smoketest_network'],
            ['set P_smoketest_port'],
            ['set D_smoketest_domain'],
            ['set RECENT_smoketest_4'],
            ['chain NAME_smoketest']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_filter', inverse=True)

    def verify_nftables(self, nftables_search, table, inverse=False, args=''):
        nftables_output = cmd(f'sudo nft {args} list table {table}')

        for search in nftables_search:
            matched = False
            for line in nftables_output.split("\n"):
                if all(item in line for item in search):
                    matched = True
                    break
            self.assertTrue(not matched if inverse else matched, msg=search)

    def test_geoip(self):
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'action', 'drop'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'source', 'geoip', 'country-code', 'se'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'source', 'geoip', 'country-code', 'gb'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'action', 'accept'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'source', 'geoip', 'country-code', 'de'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'source', 'geoip', 'country-code', 'fr'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'source', 'geoip', 'inverse-match'])

        self.cli_commit()

        nftables_search = [
            ['ip saddr @GEOIP_CC_smoketest_1', 'drop'],
            ['ip saddr != @GEOIP_CC_smoketest_2', 'return']
        ]

        # -t prevents 1000+ GeoIP elements being returned
        self.verify_nftables(nftables_search, 'ip vyos_filter', args='-t')

    def test_groups(self):
        hostmap_path = ['system', 'static-host-mapping', 'host-name']
        example_org = ['192.0.2.8', '192.0.2.10', '192.0.2.11']

        self.cli_set(hostmap_path + ['example.com', 'inet', '192.0.2.5'])
        for ips in example_org:
            self.cli_set(hostmap_path + ['example.org', 'inet', ips])

        self.cli_commit()

        self.cli_set(['firewall', 'group', 'mac-group', 'smoketest_mac', 'mac-address', '00:01:02:03:04:05'])
        self.cli_set(['firewall', 'group', 'network-group', 'smoketest_network', 'network', '172.16.99.0/24'])
        self.cli_set(['firewall', 'group', 'port-group', 'smoketest_port', 'port', '53'])
        self.cli_set(['firewall', 'group', 'port-group', 'smoketest_port', 'port', '123'])
        self.cli_set(['firewall', 'group', 'domain-group', 'smoketest_domain', 'address', 'example.com'])
        self.cli_set(['firewall', 'group', 'domain-group', 'smoketest_domain', 'address', 'example.org'])

        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'source', 'group', 'network-group', 'smoketest_network'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'destination', 'address', '172.16.10.10'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'destination', 'group', 'port-group', 'smoketest_port'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'protocol', 'tcp_udp'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'action', 'accept'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '2', 'source', 'group', 'mac-group', 'smoketest_mac'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '3', 'action', 'accept'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '3', 'source', 'group', 'domain-group', 'smoketest_domain'])

        self.cli_set(['firewall', 'interface', 'eth0', 'in', 'name', 'smoketest'])

        self.cli_commit()
        nftables_search = [
            ['iifname "eth0"', 'jump NAME_smoketest'],
            ['ip saddr @N_smoketest_network', 'ip daddr 172.16.10.10', 'th dport @P_smoketest_port', 'return'],
            ['elements = { 172.16.99.0/24 }'],
            ['elements = { 53, 123 }'],
            ['ether saddr @M_smoketest_mac', 'return'],
            ['elements = { 00:01:02:03:04:05 }'],
            ['set D_smoketest_domain'],
            ['elements = { 192.0.2.5, 192.0.2.8,'],
            ['192.0.2.10, 192.0.2.11 }'],
            ['ip saddr @D_smoketest_domain', 'return']
        ]
        self.verify_nftables(nftables_search, 'ip vyos_filter')

        self.cli_delete(['system', 'static-host-mapping'])
        self.cli_commit()

    def test_nested_groups(self):
        self.cli_set(['firewall', 'group', 'network-group', 'smoketest_network', 'network', '172.16.99.0/24'])
        self.cli_set(['firewall', 'group', 'network-group', 'smoketest_network1', 'network', '172.16.101.0/24'])
        self.cli_set(['firewall', 'group', 'network-group', 'smoketest_network1', 'include', 'smoketest_network'])
        self.cli_set(['firewall', 'group', 'port-group', 'smoketest_port', 'port', '53'])
        self.cli_set(['firewall', 'group', 'port-group', 'smoketest_port1', 'port', '123'])
        self.cli_set(['firewall', 'group', 'port-group', 'smoketest_port1', 'include', 'smoketest_port'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'source', 'group', 'network-group', 'smoketest_network1'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'destination', 'group', 'port-group', 'smoketest_port1'])
        self.cli_set(['firewall', 'name', 'smoketest', 'rule', '1', 'protocol', 'tcp_udp'])

        self.cli_set(['firewall', 'interface', 'eth0', 'in', 'name', 'smoketest'])

        self.cli_commit()

        # Test circular includes
        self.cli_set(['firewall', 'group', 'network-group', 'smoketest_network', 'include', 'smoketest_network1'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(['firewall', 'group', 'network-group', 'smoketest_network', 'include', 'smoketest_network1'])

        nftables_search = [
            ['iifname "eth0"', 'jump NAME_smoketest'],
            ['ip saddr @N_smoketest_network1', 'th dport @P_smoketest_port1', 'return'],
            ['elements = { 172.16.99.0/24, 172.16.101.0/24 }'],
            ['elements = { 53, 123 }']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_filter')

    def test_ipv4_basic_rules(self):
        name = 'smoketest'
        interface = 'eth0'
        mss_range = '501-1460'

        self.cli_set(['firewall', 'name', name, 'default-action', 'drop'])
        self.cli_set(['firewall', 'name', name, 'enable-default-log'])
        self.cli_set(['firewall', 'name', name, 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'name', name, 'rule', '1', 'source', 'address', '172.16.20.10'])
        self.cli_set(['firewall', 'name', name, 'rule', '1', 'destination', 'address', '172.16.10.10'])
        self.cli_set(['firewall', 'name', name, 'rule', '1', 'log', 'enable'])
        self.cli_set(['firewall', 'name', name, 'rule', '1', 'log-level', 'debug'])
        self.cli_set(['firewall', 'name', name, 'rule', '1', 'ttl', 'eq', '15'])
        self.cli_set(['firewall', 'name', name, 'rule', '2', 'action', 'reject'])
        self.cli_set(['firewall', 'name', name, 'rule', '2', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'name', name, 'rule', '2', 'destination', 'port', '8888'])
        self.cli_set(['firewall', 'name', name, 'rule', '2', 'log', 'enable'])
        self.cli_set(['firewall', 'name', name, 'rule', '2', 'log-level', 'err'])
        self.cli_set(['firewall', 'name', name, 'rule', '2', 'tcp', 'flags', 'syn'])
        self.cli_set(['firewall', 'name', name, 'rule', '2', 'tcp', 'flags', 'not', 'ack'])
        self.cli_set(['firewall', 'name', name, 'rule', '2', 'ttl', 'gt', '102'])
        self.cli_set(['firewall', 'name', name, 'rule', '3', 'action', 'accept'])
        self.cli_set(['firewall', 'name', name, 'rule', '3', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'name', name, 'rule', '3', 'destination', 'port', '22'])
        self.cli_set(['firewall', 'name', name, 'rule', '3', 'limit', 'rate', '5/minute'])
        self.cli_set(['firewall', 'name', name, 'rule', '3', 'log', 'disable'])
        self.cli_set(['firewall', 'name', name, 'rule', '4', 'action', 'drop'])
        self.cli_set(['firewall', 'name', name, 'rule', '4', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'name', name, 'rule', '4', 'destination', 'port', '22'])
        self.cli_set(['firewall', 'name', name, 'rule', '4', 'recent', 'count', '10'])
        self.cli_set(['firewall', 'name', name, 'rule', '4', 'recent', 'time', 'minute'])
        self.cli_set(['firewall', 'name', name, 'rule', '5', 'action', 'accept'])
        self.cli_set(['firewall', 'name', name, 'rule', '5', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'name', name, 'rule', '5', 'tcp', 'flags', 'syn'])
        self.cli_set(['firewall', 'name', name, 'rule', '5', 'tcp', 'mss', mss_range])
        self.cli_set(['firewall', 'name', name, 'rule', '5', 'inbound-interface', interface])
        self.cli_set(['firewall', 'name', name, 'rule', '6', 'action', 'return'])
        self.cli_set(['firewall', 'name', name, 'rule', '6', 'protocol', 'gre'])
        self.cli_set(['firewall', 'name', name, 'rule', '6', 'outbound-interface', interface])

        self.cli_set(['firewall', 'interface', interface, 'in', 'name', name])

        self.cli_commit()

        nftables_search = [
            [f'iifname "{interface}"', f'jump NAME_{name}'],
            ['saddr 172.16.20.10', 'daddr 172.16.10.10', 'log prefix "[smoketest-1-A]" level debug', 'ip ttl 15', 'return'],
            ['tcp flags syn / syn,ack', 'tcp dport 8888', 'log prefix "[smoketest-2-R]" level err', 'ip ttl > 102', 'reject'],
            ['tcp dport 22', 'limit rate 5/minute', 'return'],
            ['log prefix "[smoketest-default-D]"','smoketest default-action', 'drop'],
            ['tcp dport 22', 'add @RECENT_smoketest_4 { ip saddr limit rate over 10/minute burst 10 packets }', 'drop'],
            ['tcp flags & syn == syn', f'tcp option maxseg size {mss_range}', f'iifname "{interface}"'],
            ['meta l4proto gre', f'oifname "{interface}"', 'return']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_filter')

    def test_ipv4_advanced(self):
        name = 'smoketest-adv'
        name2 = 'smoketest-adv2'
        interface = 'eth0'

        self.cli_set(['firewall', 'name', name, 'default-action', 'drop'])
        self.cli_set(['firewall', 'name', name, 'enable-default-log'])

        self.cli_set(['firewall', 'name', name, 'rule', '6', 'action', 'accept'])
        self.cli_set(['firewall', 'name', name, 'rule', '6', 'packet-length', '64'])
        self.cli_set(['firewall', 'name', name, 'rule', '6', 'packet-length', '512'])
        self.cli_set(['firewall', 'name', name, 'rule', '6', 'packet-length', '1024'])
        self.cli_set(['firewall', 'name', name, 'rule', '6', 'dscp', '17'])
        self.cli_set(['firewall', 'name', name, 'rule', '6', 'dscp', '52'])

        self.cli_set(['firewall', 'name', name, 'rule', '7', 'action', 'accept'])
        self.cli_set(['firewall', 'name', name, 'rule', '7', 'packet-length', '1-30000'])
        self.cli_set(['firewall', 'name', name, 'rule', '7', 'packet-length-exclude', '60000-65535'])
        self.cli_set(['firewall', 'name', name, 'rule', '7', 'dscp', '3-11'])
        self.cli_set(['firewall', 'name', name, 'rule', '7', 'dscp-exclude', '21-25'])

        self.cli_set(['firewall', 'name', name2, 'default-action', 'jump'])
        self.cli_set(['firewall', 'name', name2, 'default-jump-target', name])
        self.cli_set(['firewall', 'name', name2, 'enable-default-log'])
        self.cli_set(['firewall', 'name', name2, 'rule', '1', 'source', 'address', '198.51.100.1'])
        self.cli_set(['firewall', 'name', name2, 'rule', '1', 'action', 'jump'])
        self.cli_set(['firewall', 'name', name2, 'rule', '1', 'jump-target', name])

        self.cli_set(['firewall', 'interface', interface, 'in', 'name', name])

        self.cli_commit()

        nftables_search = [
            [f'iifname "{interface}"', f'jump NAME_{name}'],
            ['ip length { 64, 512, 1024 }', 'ip dscp { 0x11, 0x34 }', 'return'],
            ['ip length 1-30000', 'ip length != 60000-65535', 'ip dscp 0x03-0x0b', 'ip dscp != 0x15-0x19', 'return'],
            [f'log prefix "[{name}-default-D]"', 'drop'],
            ['ip saddr 198.51.100.1', f'jump NAME_{name}'],
            [f'log prefix "[{name2}-default-J]"', f'jump NAME_{name}']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_filter')

    def test_ipv6_basic_rules(self):
        name = 'v6-smoketest'
        interface = 'eth0'

        self.cli_set(['firewall', 'ipv6-name', name, 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv6-name', name, 'enable-default-log'])

        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '1', 'source', 'address', '2002::1'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '1', 'destination', 'address', '2002::1:1'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '1', 'log', 'enable'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '1', 'log-level', 'crit'])

        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '2', 'action', 'reject'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '2', 'protocol', 'tcp_udp'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '2', 'destination', 'port', '8888'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '2', 'inbound-interface', interface])

        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '3', 'action', 'return'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '3', 'protocol', 'gre'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '3', 'outbound-interface', interface])

        self.cli_set(['firewall', 'interface', interface, 'in', 'ipv6-name', name])

        self.cli_commit()

        nftables_search = [
            [f'iifname "{interface}"', f'jump NAME6_{name}'],
            ['saddr 2002::1', 'daddr 2002::1:1', 'log prefix "[v6-smoketest-1-A]" level crit', 'return'],
            ['meta l4proto { tcp, udp }', 'th dport 8888', f'iifname "{interface}"', 'reject'],
            ['meta l4proto gre', f'oifname "{interface}"', 'return'],
            ['smoketest default-action', f'log prefix "[{name}-default-D]"', 'drop']
        ]

        self.verify_nftables(nftables_search, 'ip6 vyos_filter')

    def test_ipv6_advanced(self):
        name = 'v6-smoketest-adv'
        name2 = 'v6-smoketest-adv2'
        interface = 'eth0'

        self.cli_set(['firewall', 'ipv6-name', name, 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv6-name', name, 'enable-default-log'])

        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '3', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '3', 'packet-length', '65'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '3', 'packet-length', '513'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '3', 'packet-length', '1025'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '3', 'dscp', '18'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '3', 'dscp', '53'])

        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '4', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '4', 'packet-length', '1-1999'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '4', 'packet-length-exclude', '60000-65535'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '4', 'dscp', '4-14'])
        self.cli_set(['firewall', 'ipv6-name', name, 'rule', '4', 'dscp-exclude', '31-35'])

        self.cli_set(['firewall', 'ipv6-name', name2, 'default-action', 'jump'])
        self.cli_set(['firewall', 'ipv6-name', name2, 'default-jump-target', name])
        self.cli_set(['firewall', 'ipv6-name', name2, 'enable-default-log'])
        self.cli_set(['firewall', 'ipv6-name', name2, 'rule', '1', 'source', 'address', '2001:db8::/64'])
        self.cli_set(['firewall', 'ipv6-name', name2, 'rule', '1', 'action', 'jump'])
        self.cli_set(['firewall', 'ipv6-name', name2, 'rule', '1', 'jump-target', name])

        self.cli_set(['firewall', 'interface', interface, 'in', 'ipv6-name', name])

        self.cli_commit()

        nftables_search = [
            [f'iifname "{interface}"', f'jump NAME6_{name}'],
            ['ip6 length { 65, 513, 1025 }', 'ip6 dscp { af21, 0x35 }', 'return'],
            ['ip6 length 1-1999', 'ip6 length != 60000-65535', 'ip6 dscp 0x04-0x0e', 'ip6 dscp != 0x1f-0x23', 'return'],
            [f'log prefix "[{name}-default-D]"', 'drop'],
            ['ip6 saddr 2001:db8::/64', f'jump NAME6_{name}'],
            [f'log prefix "[{name2}-default-J]"', f'jump NAME6_{name}']
        ]

        self.verify_nftables(nftables_search, 'ip6 vyos_filter')

    def test_state_policy(self):
        self.cli_set(['firewall', 'state-policy', 'established', 'action', 'accept'])
        self.cli_set(['firewall', 'state-policy', 'related', 'action', 'accept'])
        self.cli_set(['firewall', 'state-policy', 'invalid', 'action', 'drop'])

        self.cli_commit()

        chains = {
            'ip vyos_filter': ['VYOS_FW_FORWARD', 'VYOS_FW_OUTPUT', 'VYOS_FW_LOCAL'],
            'ip6 vyos_filter': ['VYOS_FW6_FORWARD', 'VYOS_FW6_OUTPUT', 'VYOS_FW6_LOCAL']
        }

        for table in ['ip vyos_filter', 'ip6 vyos_filter']:
            for chain in chains[table]:
                nftables_output = cmd(f'sudo nft list chain {table} {chain}')
                self.assertTrue('jump VYOS_STATE_POLICY' in nftables_output)

    def test_ipv4_state_and_status_rules(self):
        name = 'smoketest-state'
        interface = 'eth0'

        self.cli_set(['firewall', 'name', name, 'default-action', 'drop'])
        self.cli_set(['firewall', 'name', name, 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'name', name, 'rule', '1', 'state', 'established', 'enable'])
        self.cli_set(['firewall', 'name', name, 'rule', '1', 'state', 'related', 'enable'])
        self.cli_set(['firewall', 'name', name, 'rule', '2', 'action', 'reject'])
        self.cli_set(['firewall', 'name', name, 'rule', '2', 'state', 'invalid', 'enable'])
        self.cli_set(['firewall', 'name', name, 'rule', '3', 'action', 'accept'])
        self.cli_set(['firewall', 'name', name, 'rule', '3', 'state', 'new', 'enable'])

        self.cli_set(['firewall', 'name', name, 'rule', '3', 'connection-status', 'nat', 'destination'])
        self.cli_set(['firewall', 'name', name, 'rule', '4', 'action', 'accept'])
        self.cli_set(['firewall', 'name', name, 'rule', '4', 'state', 'new', 'enable'])
        self.cli_set(['firewall', 'name', name, 'rule', '4', 'state', 'established', 'enable'])
        self.cli_set(['firewall', 'name', name, 'rule', '4', 'connection-status', 'nat', 'source'])

        self.cli_set(['firewall', 'interface', interface, 'in', 'name', name])

        self.cli_commit()

        nftables_search = [
            [f'iifname "{interface}"', f'jump NAME_{name}'],
            ['ct state { established, related }', 'return'],
            ['ct state invalid', 'reject'],
            ['ct state new', 'ct status dnat', 'return'],
            ['ct state { established, new }', 'ct status snat', 'return'],
            ['drop', f'comment "{name} default-action drop"']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_filter')

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

    def test_zone_basic(self):
        self.cli_set(['firewall', 'name', 'smoketest', 'default-action', 'drop'])
        self.cli_set(['firewall', 'zone', 'smoketest-eth0', 'interface', 'eth0'])
        self.cli_set(['firewall', 'zone', 'smoketest-eth0', 'from', 'smoketest-local', 'firewall', 'name', 'smoketest'])
        self.cli_set(['firewall', 'zone', 'smoketest-local', 'local-zone'])
        self.cli_set(['firewall', 'zone', 'smoketest-local', 'from', 'smoketest-eth0', 'firewall', 'name', 'smoketest'])

        self.cli_commit()

        nftables_search = [
            ['chain VZONE_smoketest-eth0'],
            ['chain VZONE_smoketest-local_IN'],
            ['chain VZONE_smoketest-local_OUT'],
            ['oifname "eth0"', 'jump VZONE_smoketest-eth0'],
            ['jump VZONE_smoketest-local_IN'],
            ['jump VZONE_smoketest-local_OUT'],
            ['iifname "eth0"', 'jump NAME_smoketest'],
            ['oifname "eth0"', 'jump NAME_smoketest']
        ]

        nftables_output = cmd('sudo nft list table ip vyos_filter')

        for search in nftables_search:
            matched = False
            for line in nftables_output.split("\n"):
                if all(item in line for item in search):
                    matched = True
                    break
            self.assertTrue(matched)

if __name__ == '__main__':
    unittest.main(verbosity=2)
