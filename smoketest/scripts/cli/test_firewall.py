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

from glob import glob
from time import sleep

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.process import run
from vyos.utils.file import read_file

sysfs_config = {
    'all_ping': {'sysfs': '/proc/sys/net/ipv4/icmp_echo_ignore_all', 'default': '0', 'test_value': 'disable'},
    'broadcast_ping': {'sysfs': '/proc/sys/net/ipv4/icmp_echo_ignore_broadcasts', 'default': '1', 'test_value': 'enable'},
    'directed_broadcast': {'sysfs': '/proc/sys/net/ipv4/conf/all/bc_forwarding', 'default': '1', 'test_value': 'disable'},
    'ip_src_route': {'sysfs': '/proc/sys/net/ipv4/conf/*/accept_source_route', 'default': '0', 'test_value': 'enable'},
    'ipv6_receive_redirects': {'sysfs': '/proc/sys/net/ipv6/conf/*/accept_redirects', 'default': '0', 'test_value': 'enable'},
    'ipv6_src_route': {'sysfs': '/proc/sys/net/ipv6/conf/*/accept_source_route', 'default': '-1', 'test_value': 'enable'},
    'log_martians': {'sysfs': '/proc/sys/net/ipv4/conf/all/log_martians', 'default': '1', 'test_value': 'disable'},
    'receive_redirects': {'sysfs': '/proc/sys/net/ipv4/conf/*/accept_redirects', 'default': '0', 'test_value': 'enable'},
    'send_redirects': {'sysfs': '/proc/sys/net/ipv4/conf/*/send_redirects', 'default': '1', 'test_value': 'disable'},
    'syn_cookies': {'sysfs': '/proc/sys/net/ipv4/tcp_syncookies', 'default': '1', 'test_value': 'disable'},
    'twa_hazards_protection': {'sysfs': '/proc/sys/net/ipv4/tcp_rfc1337', 'default': '0', 'test_value': 'enable'}
}

def get_sysctl(parameter):
    tmp = parameter.replace(r'.', r'/')
    return read_file(f'/proc/sys/{tmp}')

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

    def wait_for_domain_resolver(self, table, set_name, element, max_wait=10):
        # Resolver no longer blocks commit, need to wait for daemon to populate set
        count = 0
        while count < max_wait:
            code = run(f'sudo nft get element {table} {set_name} {{ {element} }}')
            if code == 0:
                return True
            count += 1
            sleep(1)
        return False

    def test_geoip(self):
        self.cli_set(['firewall', 'ipv4', 'name', 'smoketest', 'rule', '1', 'action', 'drop'])
        self.cli_set(['firewall', 'ipv4', 'name', 'smoketest', 'rule', '1', 'source', 'geoip', 'country-code', 'se'])
        self.cli_set(['firewall', 'ipv4', 'name', 'smoketest', 'rule', '1', 'source', 'geoip', 'country-code', 'gb'])
        self.cli_set(['firewall', 'ipv4', 'name', 'smoketest', 'rule', '2', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'name', 'smoketest', 'rule', '2', 'source', 'geoip', 'country-code', 'de'])
        self.cli_set(['firewall', 'ipv4', 'name', 'smoketest', 'rule', '2', 'source', 'geoip', 'country-code', 'fr'])
        self.cli_set(['firewall', 'ipv4', 'name', 'smoketest', 'rule', '2', 'source', 'geoip', 'inverse-match'])

        self.cli_commit()

        nftables_search = [
            ['ip saddr @GEOIP_CC_name_smoketest_1', 'drop'],
            ['ip saddr != @GEOIP_CC_name_smoketest_2', 'accept']
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
        self.cli_set(['firewall', 'group', 'interface-group', 'smoketest_interface', 'interface', 'eth0'])
        self.cli_set(['firewall', 'group', 'interface-group', 'smoketest_interface', 'interface', 'vtun0'])

        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '1', 'source', 'group', 'network-group', 'smoketest_network'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '1', 'destination', 'address', '172.16.10.10'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '1', 'destination', 'group', 'port-group', 'smoketest_port'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '1', 'protocol', 'tcp_udp'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '2', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '2', 'source', 'group', 'mac-group', 'smoketest_mac'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '3', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '3', 'source', 'group', 'domain-group', 'smoketest_domain'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '4', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '4', 'outbound-interface', 'group', '!smoketest_interface'])

        self.cli_commit()

        self.wait_for_domain_resolver('ip vyos_filter', 'D_smoketest_domain', '192.0.2.5')

        nftables_search = [
            ['ip saddr @N_smoketest_network', 'ip daddr 172.16.10.10', 'th dport @P_smoketest_port', 'accept'],
            ['elements = { 172.16.99.0/24 }'],
            ['elements = { 53, 123 }'],
            ['ether saddr @M_smoketest_mac', 'accept'],
            ['elements = { 00:01:02:03:04:05 }'],
            ['set D_smoketest_domain'],
            ['elements = { 192.0.2.5, 192.0.2.8,'],
            ['192.0.2.10, 192.0.2.11 }'],
            ['ip saddr @D_smoketest_domain', 'accept'],
            ['oifname != @I_smoketest_interface', 'accept']
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
        self.cli_set(['firewall', 'ipv4', 'name', 'smoketest', 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'name', 'smoketest', 'rule', '1', 'source', 'group', 'network-group', 'smoketest_network1'])
        self.cli_set(['firewall', 'ipv4', 'name', 'smoketest', 'rule', '1', 'destination', 'group', 'port-group', 'smoketest_port1'])
        self.cli_set(['firewall', 'ipv4', 'name', 'smoketest', 'rule', '1', 'protocol', 'tcp_udp'])

        self.cli_commit()

        # Test circular includes
        self.cli_set(['firewall', 'group', 'network-group', 'smoketest_network', 'include', 'smoketest_network1'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(['firewall', 'group', 'network-group', 'smoketest_network', 'include', 'smoketest_network1'])

        nftables_search = [
            ['ip saddr @N_smoketest_network1', 'th dport @P_smoketest_port1', 'accept'],
            ['elements = { 172.16.99.0/24, 172.16.101.0/24 }'],
            ['elements = { 53, 123 }']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_filter')

    def test_ipv4_basic_rules(self):
        name = 'smoketest'
        interface = 'eth0'
        interface_inv = '!eth0'
        interface_wc = 'l2tp*'
        mss_range = '501-1460'
        conn_mark = '555'

        self.cli_set(['firewall', 'ipv4', 'name', name, 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'default-log'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '1', 'source', 'address', '172.16.20.10'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '1', 'destination', 'address', '172.16.10.10'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '1', 'log'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '1', 'log-options', 'level', 'debug'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '1', 'ttl', 'eq', '15'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '2', 'action', 'reject'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '2', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '2', 'destination', 'port', '8888'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '2', 'log'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '2', 'log-options', 'level', 'err'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '2', 'tcp', 'flags', 'syn'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '2', 'tcp', 'flags', 'not', 'ack'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '2', 'ttl', 'gt', '102'])

        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'default-log'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '3', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '3', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '3', 'destination', 'port', '22'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '3', 'limit', 'rate', '5/minute'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '3', 'log'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '4', 'action', 'drop'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '4', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '4', 'destination', 'port', '22'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '4', 'recent', 'count', '10'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '4', 'recent', 'time', 'minute'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '4', 'packet-type', 'host'])

        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '5', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '5', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '5', 'tcp', 'flags', 'syn'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '5', 'tcp', 'mss', mss_range])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '5', 'packet-type', 'broadcast'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '5', 'inbound-interface', 'name', interface_wc])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '6', 'action', 'return'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '6', 'protocol', 'gre'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '6', 'connection-mark', conn_mark])

        self.cli_set(['firewall', 'ipv4', 'output', 'filter', 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv4', 'output', 'filter', 'default-log'])
        self.cli_set(['firewall', 'ipv4', 'output', 'filter', 'rule', '5', 'action', 'drop'])
        self.cli_set(['firewall', 'ipv4', 'output', 'filter', 'rule', '5', 'protocol', 'gre'])
        self.cli_set(['firewall', 'ipv4', 'output', 'filter', 'rule', '5', 'outbound-interface', 'name', interface_inv])
        self.cli_set(['firewall', 'ipv4', 'output', 'filter', 'rule', '6', 'action', 'return'])
        self.cli_set(['firewall', 'ipv4', 'output', 'filter', 'rule', '6', 'protocol', 'icmp'])
        self.cli_set(['firewall', 'ipv4', 'output', 'filter', 'rule', '6', 'connection-mark', conn_mark])

        self.cli_set(['firewall', 'ipv4', 'output', 'raw', 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv4', 'output', 'raw', 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'output', 'raw', 'rule', '1', 'protocol', 'udp'])

        self.cli_set(['firewall', 'ipv4', 'prerouting', 'raw', 'rule', '1', 'action', 'notrack'])
        self.cli_set(['firewall', 'ipv4', 'prerouting', 'raw', 'rule', '1', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'ipv4', 'prerouting', 'raw', 'rule', '1', 'destination', 'port', '23'])

        self.cli_commit()

        mark_hex = "{0:#010x}".format(int(conn_mark))

        nftables_search = [
            ['chain VYOS_FORWARD_filter'],
            ['type filter hook forward priority filter; policy accept;'],
            ['tcp dport 22', 'limit rate 5/minute', 'accept'],
            ['tcp dport 22', 'add @RECENT_FWD_filter_4 { ip saddr limit rate over 10/minute burst 10 packets }', 'meta pkttype host', 'drop'],
            ['log prefix "[ipv4-FWD-filter-default-D]"','FWD-filter default-action drop', 'drop'],
            ['chain VYOS_INPUT_filter'],
            ['type filter hook input priority filter; policy accept;'],
            ['tcp flags & syn == syn', f'tcp option maxseg size {mss_range}', f'iifname "{interface_wc}"', 'meta pkttype broadcast', 'accept'],
            ['meta l4proto gre', f'ct mark {mark_hex}', 'return'],
            ['INP-filter default-action accept', 'accept'],
            ['chain VYOS_OUTPUT_filter'],
            ['type filter hook output priority filter; policy accept;'],
            ['meta l4proto gre', f'oifname != "{interface}"', 'drop'],
            ['meta l4proto icmp', f'ct mark {mark_hex}', 'return'],
            ['log prefix "[ipv4-OUT-filter-default-D]"','OUT-filter default-action drop', 'drop'],
            ['chain VYOS_OUTPUT_raw'],
            ['type filter hook output priority raw; policy accept;'],
            ['udp', 'accept'],
            ['OUT-raw default-action drop', 'drop'],
            ['chain VYOS_PREROUTING_raw'],
            ['type filter hook prerouting priority raw; policy accept;'],
            ['tcp dport 23', 'notrack'],
            ['PRE-raw default-action accept', 'accept'],
            ['chain NAME_smoketest'],
            ['saddr 172.16.20.10', 'daddr 172.16.10.10', 'log prefix "[ipv4-NAM-smoketest-1-A]" log level debug', 'ip ttl 15', 'accept'],
            ['tcp flags syn / syn,ack', 'tcp dport 8888', 'log prefix "[ipv4-NAM-smoketest-2-R]" log level err', 'ip ttl > 102', 'reject'],
            ['log prefix "[ipv4-smoketest-default-D]"','smoketest default-action', 'drop']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_filter')

    def test_ipv4_advanced(self):
        name = 'smoketest-adv'
        name2 = 'smoketest-adv2'
        interface = 'eth0'

        self.cli_set(['firewall', 'ipv4', 'name', name, 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'default-log'])

        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '6', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '6', 'packet-length', '64'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '6', 'packet-length', '512'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '6', 'packet-length', '1024'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '6', 'dscp', '17'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '6', 'dscp', '52'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '6', 'log'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '6', 'log-options', 'group', '66'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '6', 'log-options', 'snapshot-length', '6666'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '6', 'log-options', 'queue-threshold','32000'])

        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '7', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '7', 'packet-length', '1-30000'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '7', 'packet-length-exclude', '60000-65535'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '7', 'dscp', '3-11'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '7', 'dscp-exclude', '21-25'])

        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '1', 'source', 'address', '198.51.100.1'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '1', 'mark', '1010'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '1', 'action', 'jump'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '1', 'jump-target', name])

        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '2', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '2', 'mark', '!98765'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '2', 'action', 'queue'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '2', 'queue', '3'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '3', 'protocol', 'udp'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '3', 'action', 'queue'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '3', 'queue-options', 'fanout'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '3', 'queue-options', 'bypass'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '3', 'queue', '0-15'])

        self.cli_commit()

        nftables_search = [
            ['chain VYOS_FORWARD_filter'],
            ['type filter hook forward priority filter; policy accept;'],
            ['ip saddr 198.51.100.1', 'meta mark 0x000003f2', f'jump NAME_{name}'],
            ['FWD-filter default-action drop', 'drop'],
            ['chain VYOS_INPUT_filter'],
            ['type filter hook input priority filter; policy accept;'],
            ['meta mark != 0x000181cd', 'meta l4proto tcp','queue to 3'],
            ['meta l4proto udp','queue flags bypass,fanout to 0-15'],
            ['INP-filter default-action accept', 'accept'],
            [f'chain NAME_{name}'],
            ['ip length { 64, 512, 1024 }', 'ip dscp { 0x11, 0x34 }', f'log prefix "[ipv4-NAM-{name}-6-A]" log group 66 snaplen 6666 queue-threshold 32000', 'accept'],
            ['ip length 1-30000', 'ip length != 60000-65535', 'ip dscp 0x03-0x0b', 'ip dscp != 0x15-0x19', 'accept'],
            [f'log prefix "[ipv4-{name}-default-D]"', 'drop']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_filter')

    def test_ipv4_synproxy(self):
        tcp_mss = '1460'
        tcp_wscale = '7'
        dport = '22'

        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '10', 'action', 'drop'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '10', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '10', 'destination', 'port', dport])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '10', 'synproxy', 'tcp', 'mss', tcp_mss])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '10', 'synproxy', 'tcp', 'window-scale', tcp_wscale])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '10', 'action', 'synproxy'])

        self.cli_commit()

        nftables_search = [
            [f'tcp dport {dport} ct state invalid,untracked', f'synproxy mss {tcp_mss} wscale {tcp_wscale} timestamp sack-perm']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_filter')


    def test_ipv4_mask(self):
        name = 'smoketest-mask'
        interface = 'eth0'

        self.cli_set(['firewall', 'group', 'address-group', 'mask_group', 'address', '1.1.1.1'])

        self.cli_set(['firewall', 'ipv4', 'name', name, 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'default-log'])

        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '1', 'action', 'drop'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '1', 'destination', 'address', '0.0.1.2'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '1', 'destination', 'address-mask', '0.0.255.255'])

        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '2', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '2', 'source', 'address', '!0.0.3.4'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '2', 'source', 'address-mask', '0.0.255.255'])

        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '3', 'action', 'drop'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '3', 'source', 'group', 'address-group', 'mask_group'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '3', 'source', 'address-mask', '0.0.255.255'])

        self.cli_commit()

        nftables_search = [
            [f'daddr & 0.0.255.255 == 0.0.1.2'],
            [f'saddr & 0.0.255.255 != 0.0.3.4'],
            [f'saddr & 0.0.255.255 == @A_mask_group']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_filter')

    def test_ipv4_dynamic_groups(self):
        group01 = 'knock01'
        group02 = 'allowed'

        self.cli_set(['firewall', 'group', 'dynamic-group', 'address-group', group01])
        self.cli_set(['firewall', 'group', 'dynamic-group', 'address-group', group02])

        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '10', 'action', 'drop'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '10', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '10', 'destination', 'port', '5151'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '10', 'add-address-to-group', 'source-address', 'address-group', group01])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '10', 'add-address-to-group', 'source-address', 'timeout', '30s'])

        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '20', 'action', 'drop'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '20', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '20', 'destination', 'port', '7272'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '20', 'source', 'group', 'dynamic-address-group', group01])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '20', 'add-address-to-group', 'source-address', 'address-group', group02])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '20', 'add-address-to-group', 'source-address', 'timeout', '5m'])

        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '30', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '30', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '30', 'destination', 'port', '22'])
        self.cli_set(['firewall', 'ipv4', 'input', 'filter', 'rule', '30', 'source', 'group', 'dynamic-address-group', group02])

        self.cli_commit()

        nftables_search = [
            [f'DA_{group01}'],
            [f'DA_{group02}'],
            ['type ipv4_addr'],
            ['flags dynamic,timeout'],
            ['chain VYOS_INPUT_filter {'],
            ['type filter hook input priority filter', 'policy accept'],
            ['tcp dport 5151', f'update @DA_{group01}', '{ ip saddr timeout 30s }', 'drop'],
            ['tcp dport 7272', f'ip saddr @DA_{group01}', f'update @DA_{group02}', '{ ip saddr timeout 5m }', 'drop'],
            ['tcp dport 22', f'ip saddr @DA_{group02}', 'accept']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_filter')

    def test_ipv6_basic_rules(self):
        name = 'v6-smoketest'
        interface = 'eth0'

        self.cli_set(['firewall', 'global-options', 'state-policy', 'established', 'action', 'accept'])
        self.cli_set(['firewall', 'global-options', 'state-policy', 'related', 'action', 'accept'])
        self.cli_set(['firewall', 'global-options', 'state-policy', 'invalid', 'action', 'drop'])

        self.cli_set(['firewall', 'ipv6', 'name', name, 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'default-log'])

        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '1', 'source', 'address', '2002::1'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '1', 'destination', 'address', '2002::1:1'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '1', 'log'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '1', 'log-options', 'level', 'crit'])

        self.cli_set(['firewall', 'ipv6', 'forward', 'filter', 'default-action', 'accept'])
        self.cli_set(['firewall', 'ipv6', 'forward', 'filter', 'default-log'])
        self.cli_set(['firewall', 'ipv6', 'forward', 'filter', 'rule', '2', 'action', 'reject'])
        self.cli_set(['firewall', 'ipv6', 'forward', 'filter', 'rule', '2', 'protocol', 'tcp_udp'])
        self.cli_set(['firewall', 'ipv6', 'forward', 'filter', 'rule', '2', 'destination', 'port', '8888'])
        self.cli_set(['firewall', 'ipv6', 'forward', 'filter', 'rule', '2', 'inbound-interface', 'name', interface])

        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '3', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '3', 'protocol', 'udp'])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '3', 'source', 'address', '2002::1:2'])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '3', 'inbound-interface', 'name', interface])

        self.cli_set(['firewall', 'ipv6', 'output', 'filter', 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv6', 'output', 'filter', 'default-log'])
        self.cli_set(['firewall', 'ipv6', 'output', 'filter', 'rule', '3', 'action', 'return'])
        self.cli_set(['firewall', 'ipv6', 'output', 'filter', 'rule', '3', 'protocol', 'gre'])
        self.cli_set(['firewall', 'ipv6', 'output', 'filter', 'rule', '3', 'outbound-interface', 'name', interface])

        self.cli_set(['firewall', 'ipv6', 'output', 'raw', 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv6', 'output', 'raw', 'rule', '1', 'action', 'notrack'])
        self.cli_set(['firewall', 'ipv6', 'output', 'raw', 'rule', '1', 'protocol', 'udp'])

        self.cli_set(['firewall', 'ipv6', 'prerouting', 'raw', 'rule', '1', 'action', 'drop'])
        self.cli_set(['firewall', 'ipv6', 'prerouting', 'raw', 'rule', '1', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'ipv6', 'prerouting', 'raw', 'rule', '1', 'destination', 'port', '23'])

        self.cli_commit()

        nftables_search = [
            ['chain VYOS_IPV6_FORWARD_filter'],
            ['type filter hook forward priority filter; policy accept;'],
            ['meta l4proto { tcp, udp }', 'th dport 8888', f'iifname "{interface}"', 'reject'],
            ['log prefix "[ipv6-FWD-filter-default-A]"','FWD-filter default-action accept', 'accept'],
            ['chain VYOS_IPV6_INPUT_filter'],
            ['type filter hook input priority filter; policy accept;'],
            ['meta l4proto udp', 'ip6 saddr 2002::1:2', f'iifname "{interface}"', 'accept'],
            ['INP-filter default-action accept', 'accept'],
            ['chain VYOS_IPV6_OUTPUT_filter'],
            ['type filter hook output priority filter; policy accept;'],
            ['meta l4proto gre', f'oifname "{interface}"', 'return'],
            ['log prefix "[ipv6-OUT-filter-default-D]"','OUT-filter default-action drop', 'drop'],
            ['chain VYOS_IPV6_OUTPUT_raw'],
            ['type filter hook output priority raw; policy accept;'],
            ['udp', 'notrack'],
            ['OUT-raw default-action drop', 'drop'],
            ['chain VYOS_IPV6_PREROUTING_raw'],
            ['type filter hook prerouting priority raw; policy accept;'],
            ['tcp dport 23', 'drop'],
            ['PRE-raw default-action accept', 'accept'],
            [f'chain NAME6_{name}'],
            ['saddr 2002::1', 'daddr 2002::1:1', 'log prefix "[ipv6-NAM-v6-smoketest-1-A]" log level crit', 'accept'],
            [f'"{name} default-action drop"', f'log prefix "[ipv6-{name}-default-D]"', 'drop'],
            ['jump VYOS_STATE_POLICY6'],
            ['chain VYOS_STATE_POLICY6'],
            ['ct state established', 'accept'],
            ['ct state invalid', 'drop'],
            ['ct state related', 'accept']
        ]

        self.verify_nftables(nftables_search, 'ip6 vyos_filter')

    def test_ipv6_advanced(self):
        name = 'v6-smoketest-adv'
        name2 = 'v6-smoketest-adv2'
        interface = 'eth0'

        self.cli_set(['firewall', 'ipv6', 'name', name, 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'default-log'])

        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '3', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '3', 'packet-length', '65'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '3', 'packet-length', '513'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '3', 'packet-length', '1025'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '3', 'dscp', '18'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '3', 'dscp', '53'])

        self.cli_set(['firewall', 'ipv6', 'forward', 'filter', 'rule', '4', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv6', 'forward', 'filter', 'rule', '4', 'packet-length', '1-1999'])
        self.cli_set(['firewall', 'ipv6', 'forward', 'filter', 'rule', '4', 'packet-length-exclude', '60000-65535'])
        self.cli_set(['firewall', 'ipv6', 'forward', 'filter', 'rule', '4', 'dscp', '4-14'])
        self.cli_set(['firewall', 'ipv6', 'forward', 'filter', 'rule', '4', 'dscp-exclude', '31-35'])

        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'default-action', 'accept'])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '1', 'source', 'address', '2001:db8::/64'])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '1', 'mark', '!6655-7766'])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '1', 'action', 'jump'])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '1', 'jump-target', name])

        self.cli_commit()

        nftables_search = [
            ['chain VYOS_IPV6_FORWARD_filter'],
            ['type filter hook forward priority filter; policy accept;'],
            ['ip6 length 1-1999', 'ip6 length != 60000-65535', 'ip6 dscp 0x04-0x0e', 'ip6 dscp != 0x1f-0x23', 'accept'],
            ['chain VYOS_IPV6_INPUT_filter'],
            ['type filter hook input priority filter; policy accept;'],
            ['ip6 saddr 2001:db8::/64', 'meta mark != 0x000019ff-0x00001e56', f'jump NAME6_{name}'],
            [f'chain NAME6_{name}'],
            ['ip6 length { 65, 513, 1025 }', 'ip6 dscp { af21, 0x35 }', 'accept'],
            [f'log prefix "[ipv6-{name}-default-D]"', 'drop']
        ]

        self.verify_nftables(nftables_search, 'ip6 vyos_filter')

    def test_ipv6_mask(self):
        name = 'v6-smoketest-mask'
        interface = 'eth0'

        self.cli_set(['firewall', 'group', 'ipv6-address-group', 'mask_group', 'address', '::beef'])

        self.cli_set(['firewall', 'ipv6', 'name', name, 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'default-log'])

        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '1', 'action', 'drop'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '1', 'destination', 'address', '::1111:2222:3333:4444'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '1', 'destination', 'address-mask', '::ffff:ffff:ffff:ffff'])

        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '2', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '2', 'source', 'address', '!::aaaa:bbbb:cccc:dddd'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '2', 'source', 'address-mask', '::ffff:ffff:ffff:ffff'])

        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '3', 'action', 'drop'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '3', 'source', 'group', 'address-group', 'mask_group'])
        self.cli_set(['firewall', 'ipv6', 'name', name, 'rule', '3', 'source', 'address-mask', '::ffff:ffff:ffff:ffff'])

        self.cli_commit()

        nftables_search = [
            ['daddr & ::ffff:ffff:ffff:ffff == ::1111:2222:3333:4444'],
            ['saddr & ::ffff:ffff:ffff:ffff != ::aaaa:bbbb:cccc:dddd'],
            ['saddr & ::ffff:ffff:ffff:ffff == @A6_mask_group']
        ]

        self.verify_nftables(nftables_search, 'ip6 vyos_filter')

    def test_ipv6_dynamic_groups(self):
        group01 = 'knock01'
        group02 = 'allowed'

        self.cli_set(['firewall', 'group', 'dynamic-group', 'ipv6-address-group', group01])
        self.cli_set(['firewall', 'group', 'dynamic-group', 'ipv6-address-group', group02])

        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '10', 'action', 'drop'])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '10', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '10', 'destination', 'port', '5151'])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '10', 'add-address-to-group', 'source-address', 'address-group', group01])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '10', 'add-address-to-group', 'source-address', 'timeout', '30s'])

        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '20', 'action', 'drop'])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '20', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '20', 'destination', 'port', '7272'])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '20', 'source', 'group', 'dynamic-address-group', group01])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '20', 'add-address-to-group', 'source-address', 'address-group', group02])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '20', 'add-address-to-group', 'source-address', 'timeout', '5m'])

        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '30', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '30', 'protocol', 'tcp'])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '30', 'destination', 'port', '22'])
        self.cli_set(['firewall', 'ipv6', 'input', 'filter', 'rule', '30', 'source', 'group', 'dynamic-address-group', group02])

        self.cli_commit()

        nftables_search = [
            [f'DA6_{group01}'],
            [f'DA6_{group02}'],
            ['type ipv6_addr'],
            ['flags dynamic,timeout'],
            ['chain VYOS_IPV6_INPUT_filter {'],
            ['type filter hook input priority filter', 'policy accept'],
            ['tcp dport 5151', f'update @DA6_{group01}', '{ ip6 saddr timeout 30s }', 'drop'],
            ['tcp dport 7272', f'ip6 saddr @DA6_{group01}', f'update @DA6_{group02}', '{ ip6 saddr timeout 5m }', 'drop'],
            ['tcp dport 22', f'ip6 saddr @DA6_{group02}', 'accept']
        ]

        self.verify_nftables(nftables_search, 'ip6 vyos_filter')

    def test_ipv4_global_state(self):
        self.cli_set(['firewall', 'global-options', 'state-policy', 'established', 'action', 'accept'])
        self.cli_set(['firewall', 'global-options', 'state-policy', 'related', 'action', 'accept'])
        self.cli_set(['firewall', 'global-options', 'state-policy', 'invalid', 'action', 'drop'])

        self.cli_commit()

        nftables_search = [
            ['jump VYOS_STATE_POLICY'],
            ['chain VYOS_STATE_POLICY'],
            ['ct state established', 'accept'],
            ['ct state invalid', 'drop'],
            ['ct state related', 'accept']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_filter')

        # Check conntrack is enabled from state-policy
        self.verify_nftables_chain([['accept']], 'ip vyos_conntrack', 'FW_CONNTRACK')
        self.verify_nftables_chain([['accept']], 'ip6 vyos_conntrack', 'FW_CONNTRACK')

    def test_ipv4_state_and_status_rules(self):
        name = 'smoketest-state'

        self.cli_set(['firewall', 'ipv4', 'name', name, 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '1', 'state', 'established'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '1', 'state', 'related'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '2', 'action', 'reject'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '2', 'state', 'invalid'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '3', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '3', 'state', 'new'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '3', 'connection-status', 'nat', 'destination'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '4', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '4', 'state', 'new'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '4', 'state', 'established'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '4', 'connection-status', 'nat', 'source'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '5', 'action', 'accept'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '5', 'state', 'related'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '5', 'conntrack-helper', 'ftp'])
        self.cli_set(['firewall', 'ipv4', 'name', name, 'rule', '5', 'conntrack-helper', 'pptp'])

        self.cli_commit()

        nftables_search = [
            ['ct state { established, related }', 'accept'],
            ['ct state invalid', 'reject'],
            ['ct state new', 'ct status dnat', 'accept'],
            ['ct state { established, new }', 'ct status snat', 'accept'],
            ['ct state related', 'ct helper { "ftp", "pptp" }', 'accept'],
            ['drop', f'comment "{name} default-action drop"']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_filter')

        # Check conntrack
        self.verify_nftables_chain([['accept']], 'ip vyos_conntrack', 'FW_CONNTRACK')
        self.verify_nftables_chain([['return']], 'ip6 vyos_conntrack', 'FW_CONNTRACK')

    def test_bridge_basic_rules(self):
        name = 'smoketest'
        interface_in = 'eth0'
        mac_address = '00:53:00:00:00:01'
        vlan_id = '12'
        vlan_prior = '3'

        self.cli_set(['firewall', 'bridge', 'name', name, 'default-action', 'accept'])
        self.cli_set(['firewall', 'bridge', 'name', name, 'default-log'])
        self.cli_set(['firewall', 'bridge', 'name', name, 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'bridge', 'name', name, 'rule', '1', 'source', 'mac-address', mac_address])
        self.cli_set(['firewall', 'bridge', 'name', name, 'rule', '1', 'inbound-interface', 'name', interface_in])
        self.cli_set(['firewall', 'bridge', 'name', name, 'rule', '1', 'log'])
        self.cli_set(['firewall', 'bridge', 'name', name, 'rule', '1', 'log-options', 'level', 'crit'])

        self.cli_set(['firewall', 'bridge', 'forward', 'filter', 'default-action', 'drop'])
        self.cli_set(['firewall', 'bridge', 'forward', 'filter', 'default-log'])
        self.cli_set(['firewall', 'bridge', 'forward', 'filter', 'rule', '1', 'action', 'accept'])
        self.cli_set(['firewall', 'bridge', 'forward', 'filter', 'rule', '1', 'vlan', 'id', vlan_id])
        self.cli_set(['firewall', 'bridge', 'forward', 'filter', 'rule', '2', 'action', 'jump'])
        self.cli_set(['firewall', 'bridge', 'forward', 'filter', 'rule', '2', 'jump-target', name])
        self.cli_set(['firewall', 'bridge', 'forward', 'filter', 'rule', '2', 'vlan', 'priority', vlan_prior])

        self.cli_commit()

        nftables_search = [
            ['chain VYOS_FORWARD_filter'],
            ['type filter hook forward priority filter; policy accept;'],
            [f'vlan id {vlan_id}', 'accept'],
            [f'vlan pcp {vlan_prior}', f'jump NAME_{name}'],
            ['log prefix "[bri-FWD-filter-default-D]"', 'drop', 'FWD-filter default-action drop'],
            [f'chain NAME_{name}'],
            [f'ether saddr {mac_address}', f'iifname "{interface_in}"', f'log prefix "[bri-NAM-{name}-1-A]" log level crit', 'accept'],
            ['accept', f'{name} default-action accept']
        ]

        self.verify_nftables(nftables_search, 'bridge vyos_filter')

    def test_source_validation(self):
        # Strict
        self.cli_set(['firewall', 'global-options', 'source-validation', 'strict'])
        self.cli_set(['firewall', 'global-options', 'ipv6-source-validation', 'strict'])
        self.cli_commit()

        nftables_strict_search = [
            ['fib saddr . iif oif 0', 'drop']
        ]

        self.verify_nftables_chain(nftables_strict_search, 'ip raw', 'vyos_global_rpfilter')
        self.verify_nftables_chain(nftables_strict_search, 'ip6 raw', 'vyos_global_rpfilter')

        # Loose
        self.cli_set(['firewall', 'global-options', 'source-validation', 'loose'])
        self.cli_set(['firewall', 'global-options', 'ipv6-source-validation', 'loose'])
        self.cli_commit()

        nftables_loose_search = [
            ['fib saddr oif 0', 'drop']
        ]

        self.verify_nftables_chain(nftables_loose_search, 'ip raw', 'vyos_global_rpfilter')
        self.verify_nftables_chain(nftables_loose_search, 'ip6 raw', 'vyos_global_rpfilter')

    def test_sysfs(self):
        for name, conf in sysfs_config.items():
            paths = glob(conf['sysfs'])
            for path in paths:
                with open(path, 'r') as f:
                    self.assertEqual(f.read().strip(), conf['default'], msg=path)

            self.cli_set(['firewall', 'global-options', name.replace("_", "-"), conf['test_value']])

        self.cli_commit()

        for name, conf in sysfs_config.items():
            paths = glob(conf['sysfs'])
            for path in paths:
                with open(path, 'r') as f:
                    self.assertNotEqual(f.read().strip(), conf['default'], msg=path)

    def test_timeout_sysctl(self):
        timeout_config = {
            'net.netfilter.nf_conntrack_icmp_timeout' :{
                'cli'           : ['global-options', 'timeout', 'icmp'],
                'test_value'    : '180',
                'default_value' : '30',
            },
            'net.netfilter.nf_conntrack_generic_timeout' :{
                'cli'           : ['global-options', 'timeout', 'other'],
                'test_value'    : '1200',
                'default_value' : '600',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_close_wait' :{
                'cli'           : ['global-options', 'timeout', 'tcp', 'close-wait'],
                'test_value'    : '30',
                'default_value' : '60',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_close' :{
                'cli'           : ['global-options', 'timeout', 'tcp', 'close'],
                'test_value'    : '20',
                'default_value' : '10',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_established' :{
                'cli'           : ['global-options', 'timeout', 'tcp', 'established'],
                'test_value'    : '1000',
                'default_value' : '432000',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_fin_wait' :{
                'cli'           : ['global-options', 'timeout', 'tcp', 'fin-wait'],
                'test_value'    : '240',
                'default_value' : '120',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_last_ack' :{
                'cli'           : ['global-options', 'timeout', 'tcp', 'last-ack'],
                'test_value'    : '300',
                'default_value' : '30',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_syn_recv' :{
                'cli'           : ['global-options', 'timeout', 'tcp', 'syn-recv'],
                'test_value'    : '100',
                'default_value' : '60',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_syn_sent' :{
                'cli'           : ['global-options', 'timeout', 'tcp', 'syn-sent'],
                'test_value'    : '300',
                'default_value' : '120',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_time_wait' :{
                'cli'           : ['global-options', 'timeout', 'tcp', 'time-wait'],
                'test_value'    : '303',
                'default_value' : '120',
            },
            'net.netfilter.nf_conntrack_udp_timeout' :{
                'cli'           : ['global-options', 'timeout', 'udp', 'other'],
                'test_value'    : '90',
                'default_value' : '30',
            },
            'net.netfilter.nf_conntrack_udp_timeout_stream' :{
                'cli'           : ['global-options', 'timeout', 'udp', 'stream'],
                'test_value'    : '200',
                'default_value' : '180',
            },
        }

        for parameter, parameter_config in timeout_config.items():
            self.cli_set(['firewall'] + parameter_config['cli'] + [parameter_config['test_value']])

        # commit changes
        self.cli_commit()

        # validate configuration
        for parameter, parameter_config in timeout_config.items():
            tmp = parameter_config['test_value']
            self.assertEqual(get_sysctl(f'{parameter}'), tmp)

        # delete all configuration options and revert back to defaults
        self.cli_delete(['firewall', 'global-options', 'timeout'])
        self.cli_commit()

        # validate configuration
        for parameter, parameter_config in timeout_config.items():
            self.assertEqual(get_sysctl(f'{parameter}'), parameter_config['default_value'])

### Zone
    def test_zone_basic(self):
        self.cli_set(['firewall', 'ipv4', 'name', 'smoketest', 'default-action', 'drop'])
        self.cli_set(['firewall', 'ipv6', 'name', 'smoketestv6', 'default-action', 'drop'])
        self.cli_set(['firewall', 'zone', 'smoketest-eth0', 'interface', 'eth0'])
        self.cli_set(['firewall', 'zone', 'smoketest-eth0', 'from', 'smoketest-local', 'firewall', 'name', 'smoketest'])
        self.cli_set(['firewall', 'zone', 'smoketest-eth0', 'intra-zone-filtering', 'firewall', 'ipv6-name', 'smoketestv6'])
        self.cli_set(['firewall', 'zone', 'smoketest-local', 'local-zone'])
        self.cli_set(['firewall', 'zone', 'smoketest-local', 'from', 'smoketest-eth0', 'firewall', 'name', 'smoketest'])
        self.cli_set(['firewall', 'global-options', 'state-policy', 'established', 'action', 'accept'])
        self.cli_set(['firewall', 'global-options', 'state-policy', 'established', 'log'])
        self.cli_set(['firewall', 'global-options', 'state-policy', 'related', 'action', 'accept'])
        self.cli_set(['firewall', 'global-options', 'state-policy', 'invalid', 'action', 'drop'])

        self.cli_commit()

        nftables_search = [
            ['chain VYOS_ZONE_FORWARD'],
            ['type filter hook forward priority filter + 1'],
            ['chain VYOS_ZONE_OUTPUT'],
            ['type filter hook output priority filter + 1'],
            ['chain VYOS_ZONE_LOCAL'],
            ['type filter hook input priority filter + 1'],
            ['chain VZONE_smoketest-eth0'],
            ['chain VZONE_smoketest-local_IN'],
            ['chain VZONE_smoketest-local_OUT'],
            ['oifname "eth0"', 'jump VZONE_smoketest-eth0'],
            ['jump VZONE_smoketest-local_IN'],
            ['jump VZONE_smoketest-local_OUT'],
            ['iifname "eth0"', 'jump NAME_smoketest'],
            ['oifname "eth0"', 'jump NAME_smoketest'],
            ['jump VYOS_STATE_POLICY'],
            ['chain VYOS_STATE_POLICY'],
            ['ct state established', 'log prefix "[STATE-POLICY-EST-A]"', 'accept'],
            ['ct state invalid', 'drop'],
            ['ct state related', 'accept']
        ]

        nftables_search_v6 = [
            ['chain VYOS_ZONE_FORWARD'],
            ['type filter hook forward priority filter + 1'],
            ['chain VYOS_ZONE_OUTPUT'],
            ['type filter hook output priority filter + 1'],
            ['chain VYOS_ZONE_LOCAL'],
            ['type filter hook input priority filter + 1'],
            ['chain VZONE_smoketest-eth0'],
            ['chain VZONE_smoketest-local_IN'],
            ['chain VZONE_smoketest-local_OUT'],
            ['oifname "eth0"', 'jump VZONE_smoketest-eth0'],
            ['jump VZONE_smoketest-local_IN'],
            ['jump VZONE_smoketest-local_OUT'],
            ['iifname "eth0"', 'jump NAME6_smoketestv6'],
            ['jump VYOS_STATE_POLICY6'],
            ['chain VYOS_STATE_POLICY6'],
            ['ct state established', 'log prefix "[STATE-POLICY-EST-A]"', 'accept'],
            ['ct state invalid', 'drop'],
            ['ct state related', 'accept']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_filter')
        self.verify_nftables(nftables_search_v6, 'ip6 vyos_filter')

    def test_flow_offload(self):
        self.cli_set(['interfaces', 'ethernet', 'eth0', 'vif', '10'])
        self.cli_set(['firewall', 'flowtable', 'smoketest', 'interface', 'eth0.10'])
        self.cli_set(['firewall', 'flowtable', 'smoketest', 'offload', 'hardware'])

        # QEMU virtual NIC does not support hw-tc-offload
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(['firewall', 'flowtable', 'smoketest', 'offload', 'software'])

        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '1', 'action', 'offload'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '1', 'offload-target', 'smoketest'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '1', 'protocol', 'tcp_udp'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '1', 'state', 'established'])
        self.cli_set(['firewall', 'ipv4', 'forward', 'filter', 'rule', '1', 'state', 'related'])

        self.cli_set(['firewall', 'ipv6', 'forward', 'filter', 'rule', '1', 'action', 'offload'])
        self.cli_set(['firewall', 'ipv6', 'forward', 'filter', 'rule', '1', 'offload-target', 'smoketest'])
        self.cli_set(['firewall', 'ipv6', 'forward', 'filter', 'rule', '1', 'protocol', 'tcp_udp'])
        self.cli_set(['firewall', 'ipv6', 'forward', 'filter', 'rule', '1', 'state', 'established'])
        self.cli_set(['firewall', 'ipv6', 'forward', 'filter', 'rule', '1', 'state', 'related'])

        self.cli_commit()

        nftables_search = [
            ['flowtable VYOS_FLOWTABLE_smoketest'],
            ['hook ingress priority filter'],
            ['devices = { eth0.10 }'],
            ['ct state { established, related }', 'meta l4proto { tcp, udp }', 'flow add @VYOS_FLOWTABLE_smoketest'],
        ]

        self.verify_nftables(nftables_search, 'ip vyos_filter')
        self.verify_nftables(nftables_search, 'ip6 vyos_filter')

        # Check conntrack
        self.verify_nftables_chain([['accept']], 'ip vyos_conntrack', 'FW_CONNTRACK')
        self.verify_nftables_chain([['accept']], 'ip6 vyos_conntrack', 'FW_CONNTRACK')

    def test_zone_flow_offload(self):
        self.cli_set(['firewall', 'flowtable', 'smoketest', 'interface', 'eth0'])
        self.cli_set(['firewall', 'flowtable', 'smoketest', 'offload', 'hardware'])

        # QEMU virtual NIC does not support hw-tc-offload
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(['firewall', 'flowtable', 'smoketest', 'offload', 'software'])

        self.cli_set(['firewall', 'ipv4', 'name', 'smoketest', 'rule', '1', 'action', 'offload'])
        self.cli_set(['firewall', 'ipv4', 'name', 'smoketest', 'rule', '1', 'offload-target', 'smoketest'])

        self.cli_set(['firewall', 'ipv6', 'name', 'smoketest', 'rule', '1', 'action', 'offload'])
        self.cli_set(['firewall', 'ipv6', 'name', 'smoketest', 'rule', '1', 'offload-target', 'smoketest'])

        self.cli_commit()

        nftables_search = [
            ['chain NAME_smoketest'],
            ['flow add @VYOS_FLOWTABLE_smoketest']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_filter')

        nftables_search = [
            ['chain NAME6_smoketest'],
            ['flow add @VYOS_FLOWTABLE_smoketest']
        ]

        self.verify_nftables(nftables_search, 'ip6 vyos_filter')

        # Check conntrack
        self.verify_nftables_chain([['accept']], 'ip vyos_conntrack', 'FW_CONNTRACK')
        self.verify_nftables_chain([['accept']], 'ip6 vyos_conntrack', 'FW_CONNTRACK')

if __name__ == '__main__':
    unittest.main(verbosity=2)
