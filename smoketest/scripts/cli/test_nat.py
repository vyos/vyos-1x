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

import os
import re
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.process import cmdl
from vyos.utils.process import run

base_path = ['nat']
src_path = base_path + ['source']
dst_path = base_path + ['destination']
static_path = base_path + ['static']

nftables_nat_config = '/run/nftables_nat.conf'
nftables_static_nat_conf = '/run/nftables_static-nat-rules.nft'

class TestNAT(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestNAT, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()
        self.assertFalse(os.path.exists(nftables_nat_config))
        self.assertFalse(os.path.exists(nftables_static_nat_conf))
        tables = cmdl(['nft', 'list', 'tables'], sudo=True)
        self.assertNotIn('table ip vyos_nat', tables)
        self.assertNotIn('table ip vyos_static_nat', tables)
        # always forward to base class
        super().tearDown()

    def assert_commit_fails(self, message):
        # commit output wraps long lines, match the words across any whitespace
        pattern = r'\s+'.join(re.escape(word) for word in message.split())
        with self.assertRaisesRegex(ConfigSessionError, pattern):
            self.cli_commit()

    def wait_for_domain_resolver(self, table, set_name, element, max_wait=10):
        # Resolver no longer blocks commit, need to wait for daemon to populate set
        found, _ = self.wait_for_result(
            lambda: run(f'sudo nft get element {table} {set_name} {{ {element} }}'),
            0, pause=0.2, timeout=max_wait)
        return found

    def test_snat(self):
        rules = ['100', '110', '120', '130', '200', '210', '220', '230']
        outbound_iface_100 = 'eth0'
        outbound_iface_200 = 'eth1'

        nftables_search = ['jump VYOS_PRE_SNAT_HOOK']

        for rule in rules:
            network = f'192.168.{rule}.0/24'
            # depending of rule order we check either for source address for NAT
            # or configured destination address for NAT
            if int(rule) < 200:
                self.cli_set(src_path + ['rule', rule, 'source', 'address', network])
                self.cli_set(src_path + ['rule', rule, 'outbound-interface', 'name', outbound_iface_100])
                self.cli_set(src_path + ['rule', rule, 'translation', 'address', 'masquerade'])
                nftables_search.append([f'saddr {network}', f'oifname "{outbound_iface_100}"', 'masquerade'])
            else:
                self.cli_set(src_path + ['rule', rule, 'destination', 'address', network])
                self.cli_set(src_path + ['rule', rule, 'outbound-interface', 'name', outbound_iface_200])
                self.cli_set(src_path + ['rule', rule, 'exclude'])
                nftables_search.append([f'daddr {network}', f'oifname "{outbound_iface_200}"', 'return'])

        self.cli_commit()

        self.verify_nftables(nftables_search, 'ip vyos_nat')

    def test_snat_groups(self):
        address_group = 'smoketest_addr'
        address_group_member = '192.0.2.1'
        interface_group = 'smoketest_ifaces'
        interface_group_member = 'eth0'

        self.cli_set(['firewall', 'group', 'address-group', address_group, 'address', address_group_member])
        self.cli_set(['firewall', 'group', 'interface-group', interface_group, 'interface', interface_group_member])

        self.cli_set(src_path + ['rule', '100', 'source', 'group', 'address-group', address_group])
        self.cli_set(src_path + ['rule', '100', 'outbound-interface', 'group', interface_group])
        self.cli_set(src_path + ['rule', '100', 'translation', 'address', 'masquerade'])

        self.cli_set(src_path + ['rule', '110', 'source', 'group', 'address-group', address_group])
        self.cli_set(src_path + ['rule', '110', 'translation', 'address', '203.0.113.1'])

        self.cli_set(src_path + ['rule', '120', 'source', 'group', 'address-group', address_group])
        self.cli_set(src_path + ['rule', '120', 'translation', 'address', '203.0.113.111/32'])

        self.cli_commit()

        nftables_search = [
            [f'set A_{address_group}'],
            [f'elements = {{ {address_group_member} }}'],
            [f'ip saddr @A_{address_group}', f'oifname @I_{interface_group}', 'masquerade'],
            [f'ip saddr @A_{address_group}', 'snat to 203.0.113.1'],
            [f'ip saddr @A_{address_group}', 'snat prefix to 203.0.113.111/32']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_nat')

        self.cli_delete(['firewall'])

    def test_dnat(self):
        rules = ['100', '110', '120', '130', '200', '210', '220', '230']
        inbound_iface_100 = 'eth0'
        inbound_iface_200 = 'eth1'
        inbound_proto_100 = 'udp'
        inbound_proto_200 = 'tcp'

        nftables_search = ['jump VYOS_PRE_DNAT_HOOK']

        for rule in rules:
            port = f'10{rule}'
            self.cli_set(dst_path + ['rule', rule, 'source', 'port', port])
            self.cli_set(dst_path + ['rule', rule, 'translation', 'address', '192.0.2.1'])
            self.cli_set(dst_path + ['rule', rule, 'translation', 'port', port])
            rule_search = [f'dnat to 192.0.2.1:{port}']
            if int(rule) < 200:
                self.cli_set(dst_path + ['rule', rule, 'protocol', inbound_proto_100])
                self.cli_set(dst_path + ['rule', rule, 'inbound-interface', 'name', inbound_iface_100])
                rule_search.append(f'{inbound_proto_100} sport {port}')
                rule_search.append(f'iifname "{inbound_iface_100}"')
            else:
                self.cli_set(dst_path + ['rule', rule, 'protocol', inbound_proto_200])
                self.cli_set(dst_path + ['rule', rule, 'inbound-interface', 'name', inbound_iface_200])
                rule_search.append(f'{inbound_proto_200} sport {port}')
                rule_search.append(f'iifname "{inbound_iface_200}"')

            nftables_search.append(rule_search)

        self.cli_commit()

        self.verify_nftables(nftables_search, 'ip vyos_nat')

    def test_snat_required_translation_address(self):
        # T2813: Ensure translation address is specified
        rule = '5'
        self.cli_set(src_path + ['rule', rule, 'source', 'address', '192.0.2.0/24'])

        # check validate() - translation address not specified
        self.assert_commit_fails('translation requires address and/or port')

        self.cli_set(src_path + ['rule', rule, 'translation', 'address', 'masquerade'])
        self.cli_commit()

    def test_dnat_negated_addresses(self):
        # T3186: negated addresses are not accepted by nftables
        rule = '1000'
        self.cli_set(dst_path + ['rule', rule, 'destination', 'address', '!192.0.2.1'])
        self.cli_set(dst_path + ['rule', rule, 'destination', 'port', '53'])
        self.cli_set(dst_path + ['rule', rule, 'inbound-interface', 'name', 'eth0'])
        self.cli_set(dst_path + ['rule', rule, 'protocol', 'tcp_udp'])
        self.cli_set(dst_path + ['rule', rule, 'source', 'address', '!192.0.2.1'])
        self.cli_set(dst_path + ['rule', rule, 'translation', 'address', '192.0.2.1'])
        self.cli_set(dst_path + ['rule', rule, 'translation', 'port', '53'])
        self.cli_commit()

        nftables_search = [
            ['iifname "eth0"', 'meta l4proto { tcp, udp }', 'ip daddr != 192.0.2.1', 'th dport 53',
             'ip saddr != 192.0.2.1', 'dnat to 192.0.2.1:53', f'comment "DST-NAT-{rule}"'],
        ]
        self.verify_nftables(nftables_search, 'ip vyos_nat')

    def test_nat_no_rules(self):
        # T3206: deleting all rules but keep the direction 'destination' or
        # 'source' resulteds in KeyError: 'rule'.
        #
        # Test that both 'nat destination' and 'nat source' nodes can exist
        # without any rule
        self.cli_set(src_path)
        self.cli_set(dst_path)
        self.cli_set(static_path)
        self.cli_commit()

        self.verify_nftables_chain([['jump VYOS_PRE_DNAT_HOOK']], 'ip vyos_nat', 'PREROUTING')
        self.verify_nftables_chain([['jump VYOS_PRE_SNAT_HOOK']], 'ip vyos_nat', 'POSTROUTING')
        self.verify_nftables_chain([['comment']], 'ip vyos_nat', 'PREROUTING', inverse=True)
        self.verify_nftables_chain([['comment']], 'ip vyos_nat', 'POSTROUTING', inverse=True)

    def test_dnat_without_translation_address(self):
        self.cli_set(dst_path + ['rule', '1', 'inbound-interface', 'name', 'eth1'])
        self.cli_set(dst_path + ['rule', '1', 'destination', 'port', '443'])
        self.cli_set(dst_path + ['rule', '1', 'protocol', 'tcp'])
        self.cli_set(dst_path + ['rule', '1', 'packet-type', 'host'])
        self.cli_set(dst_path + ['rule', '1', 'translation', 'port', '443'])

        self.cli_commit()

        nftables_search = [
            ['iifname "eth1"', 'tcp dport 443', 'pkttype host', 'dnat to :443']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_nat')

    def test_static_nat(self):
        dst_addr_1 = '10.0.1.1'
        translate_addr_1 = '192.168.1.1'
        dst_addr_2 = '203.0.113.0/24'
        translate_addr_2 = '192.0.2.0/24'
        ifname = 'eth0'

        self.cli_set(static_path + ['rule', '10', 'destination', 'address', dst_addr_1])
        self.cli_set(static_path + ['rule', '10', 'inbound-interface', ifname])
        self.cli_set(static_path + ['rule', '10', 'translation', 'address', translate_addr_1])

        self.cli_set(static_path + ['rule', '20', 'destination', 'address', dst_addr_2])
        self.cli_set(static_path + ['rule', '20', 'inbound-interface', ifname])
        self.cli_set(static_path + ['rule', '20', 'translation', 'address', translate_addr_2])

        self.cli_set(static_path + ['rule', '30', 'destination', 'address', '203.0.114.5'])
        self.cli_set(static_path + ['rule', '30', 'inbound-interface', 'any'])
        self.cli_set(static_path + ['rule', '30', 'translation', 'address', '10.0.3.5'])
        self.cli_set(static_path + ['rule', '30', 'log'])

        self.cli_commit()

        nftables_search = [
            [f'iifname "{ifname}"', f'ip daddr {dst_addr_1}', f'dnat to {translate_addr_1}'],
            [f'oifname "{ifname}"', f'ip saddr {translate_addr_1}', f'snat to {dst_addr_1}'],
            [f'iifname "{ifname}"', f'dnat ip prefix to ip daddr map {{ {dst_addr_2} : {translate_addr_2} }}'],
            [f'oifname "{ifname}"', f'snat ip prefix to ip saddr map {{ {translate_addr_2} : {dst_addr_2} }}'],
            ['ip daddr 203.0.114.5', 'log prefix "[STATIC-DST-NAT-30]"', 'dnat to 10.0.3.5', 'comment "STATIC-DST-NAT-30"'],
            ['ip saddr 10.0.3.5', 'log prefix "[STATIC-SRC-NAT-30]"', 'snat to 203.0.114.5', 'comment "STATIC-SRC-NAT-30"'],
        ]

        self.verify_nftables(nftables_search, 'ip vyos_static_nat')
        # "any" must not restrict the rule to an interface
        self.verify_nftables([['ifname', 'STATIC-DST-NAT-30'], ['ifname', 'STATIC-SRC-NAT-30']],
                             'ip vyos_static_nat', inverse=True)

    def test_dnat_redirect(self):
        dst_addr_1 = '10.0.1.1'
        dest_port = '5122'
        protocol = 'tcp'
        redirected_port = '22'
        ifname = 'eth0'

        self.cli_set(dst_path + ['rule', '10', 'destination', 'address', dst_addr_1])
        self.cli_set(dst_path + ['rule', '10', 'destination', 'port', dest_port])
        self.cli_set(dst_path + ['rule', '10', 'protocol', protocol])
        self.cli_set(dst_path + ['rule', '10', 'inbound-interface', 'name', ifname])
        self.cli_set(dst_path + ['rule', '10', 'translation', 'redirect', 'port', redirected_port])

        self.cli_set(dst_path + ['rule', '20', 'destination', 'address', dst_addr_1])
        self.cli_set(dst_path + ['rule', '20', 'destination', 'port', dest_port])
        self.cli_set(dst_path + ['rule', '20', 'protocol', protocol])
        self.cli_set(dst_path + ['rule', '20', 'inbound-interface', 'name', ifname])
        self.cli_set(dst_path + ['rule', '20', 'translation', 'redirect'])

        self.cli_commit()

        nftables_search = [
            [f'iifname "{ifname}"', f'ip daddr {dst_addr_1}', f'{protocol} dport {dest_port}', f'redirect to :{redirected_port}'],
            [f'iifname "{ifname}"', f'ip daddr {dst_addr_1}', f'{protocol} dport {dest_port}', f'redirect']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_nat')

    def test_nat_balance(self):
        ifname = 'eth0'
        member_1 = '198.51.100.1'
        weight_1 = '10'
        member_2 = '198.51.100.2'
        weight_2 = '90'
        member_3 = '192.0.2.1'
        weight_3 = '35'
        member_4 = '192.0.2.2'
        weight_4 = '65'
        dst_port = '443'

        self.cli_set(dst_path + ['rule', '1', 'inbound-interface', 'name', ifname])
        self.cli_set(dst_path + ['rule', '1', 'protocol', 'tcp'])
        self.cli_set(dst_path + ['rule', '1', 'destination', 'port', dst_port])
        self.cli_set(dst_path + ['rule', '1', 'load-balance', 'hash', 'source-address'])
        self.cli_set(dst_path + ['rule', '1', 'load-balance', 'hash', 'source-port'])
        self.cli_set(dst_path + ['rule', '1', 'load-balance', 'hash', 'destination-address'])
        self.cli_set(dst_path + ['rule', '1', 'load-balance', 'hash', 'destination-port'])
        self.cli_set(dst_path + ['rule', '1', 'load-balance', 'backend', member_1, 'weight', weight_1])
        self.cli_set(dst_path + ['rule', '1', 'load-balance', 'backend', member_2, 'weight', weight_2])

        self.cli_set(src_path + ['rule', '1', 'outbound-interface', 'name', ifname])
        self.cli_set(src_path + ['rule', '1', 'load-balance', 'hash', 'random'])
        self.cli_set(src_path + ['rule', '1', 'load-balance', 'backend', member_3, 'weight', weight_3])
        self.cli_set(src_path + ['rule', '1', 'load-balance', 'backend', member_4, 'weight', weight_4])

        # weights not adding up to 100 must still cover the whole hash range
        self.cli_set(dst_path + ['rule', '2', 'inbound-interface', 'name', ifname])
        self.cli_set(dst_path + ['rule', '2', 'protocol', 'udp'])
        self.cli_set(dst_path + ['rule', '2', 'destination', 'port', '53'])
        self.cli_set(dst_path + ['rule', '2', 'load-balance', 'hash', 'source-address'])
        self.cli_set(dst_path + ['rule', '2', 'load-balance', 'backend', '192.0.2.51', 'weight', '50'])
        self.cli_set(dst_path + ['rule', '2', 'load-balance', 'backend', '192.0.2.52', 'weight', '40'])

        self.cli_set(src_path + ['rule', '2', 'outbound-interface', 'name', ifname])
        self.cli_set(src_path + ['rule', '2', 'protocol', 'tcp'])
        self.cli_set(src_path + ['rule', '2', 'load-balance', 'hash', 'destination-port'])
        self.cli_set(src_path + ['rule', '2', 'load-balance', 'backend', '203.0.113.1', 'weight', '1'])
        self.cli_set(src_path + ['rule', '2', 'load-balance', 'backend', '203.0.113.2', 'weight', '1'])

        # translation port and options must not end up in front of the map
        self.cli_set(dst_path + ['rule', '3', 'inbound-interface', 'name', ifname])
        self.cli_set(dst_path + ['rule', '3', 'protocol', 'tcp'])
        self.cli_set(dst_path + ['rule', '3', 'destination', 'port', '8443'])
        self.cli_set(dst_path + ['rule', '3', 'translation', 'port', '443'])
        self.cli_set(dst_path + ['rule', '3', 'translation', 'options', 'address-mapping', 'persistent'])
        self.cli_set(dst_path + ['rule', '3', 'load-balance', 'hash', 'random'])
        self.cli_set(dst_path + ['rule', '3', 'load-balance', 'backend', '192.0.2.61', 'weight', '1'])
        self.cli_set(dst_path + ['rule', '3', 'load-balance', 'backend', '192.0.2.62', 'weight', '3'])

        self.cli_commit()

        nftables_search = [
            [f'iifname "{ifname}"', f'tcp dport {dst_port}', f'dnat to jhash ip saddr . tcp sport . ip daddr . tcp dport mod 100 map', f'0-9 : {member_1}, 10-99 : {member_2}'],
            [f'oifname "{ifname}"', f'snat to numgen random mod 100 map', f'0-34 : {member_3}, 35-99 : {member_4}'],
            ['udp dport 53', 'dnat to jhash ip saddr mod 90 map { 0-49 : 192.0.2.51, 50-89 : 192.0.2.52 }', 'comment "DST-NAT-2"'],
            ['meta l4proto tcp', 'snat to jhash tcp dport mod 2 map { 0 : 203.0.113.1, 1 : 203.0.113.2 }', 'comment "SRC-NAT-2"'],
            ['tcp dport 8443', 'dnat ip to numgen random mod 4 map { 0 : 192.0.2.61 . 443, 1-3 : 192.0.2.62 . 443 } persistent', 'comment "DST-NAT-3"'],
        ]

        self.verify_nftables(nftables_search, 'ip vyos_nat')

    def test_snat_net_port_map(self):
        self.cli_set(src_path + ['rule', '10', 'protocol', 'tcp_udp'])
        self.cli_set(src_path + ['rule', '10', 'source', 'address', '100.64.0.0/25'])
        self.cli_set(src_path + ['rule', '10', 'translation', 'address', '203.0.113.0/25'])
        self.cli_set(src_path + ['rule', '10', 'translation', 'port', '1025-3072'])

        self.cli_set(src_path + ['rule', '20', 'protocol', 'tcp_udp'])
        self.cli_set(src_path + ['rule', '20', 'source', 'address', '100.64.0.128/25'])
        self.cli_set(src_path + ['rule', '20', 'translation', 'address', '203.0.113.128/25'])
        self.cli_set(src_path + ['rule', '20', 'translation', 'port', '1025-3072'])

        self.cli_commit()

        nftables_search = [
            ['meta l4proto { tcp, udp }', 'snat ip prefix to ip saddr map { 100.64.0.0/25 : 203.0.113.0/25 . 1025-3072 }', 'comment "SRC-NAT-10"'],
            ['meta l4proto { tcp, udp }', 'snat ip prefix to ip saddr map { 100.64.0.128/25 : 203.0.113.128/25 . 1025-3072 }', 'comment "SRC-NAT-20"']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_nat')

    def test_nat_fqdn(self):
        source_domain = 'vyos.dev'
        source_address = '192.0.2.10'
        destination_domain = 'vyos.io'
        destination_address = '192.0.2.20'
        hostmap_path = ['system', 'static-host-mapping', 'host-name']

        self.cli_set(hostmap_path + [source_domain, 'inet', source_address])
        self.cli_set(hostmap_path + [destination_domain, 'inet', destination_address])

        self.cli_set(src_path + ['rule', '1', 'outbound-interface', 'name', 'eth0'])
        self.cli_set(src_path + ['rule', '1', 'source', 'fqdn', source_domain])
        self.cli_set(src_path + ['rule', '1', 'translation', 'address', 'masquerade'])

        self.cli_set(dst_path + ['rule', '1', 'destination', 'fqdn', destination_domain])
        self.cli_set(dst_path + ['rule', '1', 'source', 'fqdn', source_domain])
        self.cli_set(dst_path + ['rule', '1', 'destination', 'port', '5122'])
        self.cli_set(dst_path + ['rule', '1', 'protocol', 'tcp'])
        self.cli_set(dst_path + ['rule', '1', 'translation', 'address', '198.51.100.1'])
        self.cli_set(dst_path + ['rule', '1', 'translation', 'port', '22'])


        self.cli_commit()

        nftables_search = [
            ['set FQDN_nat_destination_1_d'],
            ['set FQDN_nat_source_1_s'],
            ['oifname "eth0"', 'ip saddr @FQDN_nat_source_1_s', 'masquerade', 'comment "SRC-NAT-1"'],
            ['tcp dport 5122', 'ip saddr @FQDN_nat_destination_1_s', 'ip daddr @FQDN_nat_destination_1_d', 'dnat to 198.51.100.1:22', 'comment "DST-NAT-1"']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_nat')

        self.assertTrue(self.wait_for_domain_resolver('ip vyos_nat', 'FQDN_nat_source_1_s', source_address))
        self.assertTrue(self.wait_for_domain_resolver('ip vyos_nat', 'FQDN_nat_destination_1_s', source_address))
        self.assertTrue(self.wait_for_domain_resolver('ip vyos_nat', 'FQDN_nat_destination_1_d', destination_address))

        self.cli_delete(['system', 'static-host-mapping'])
    def test_snat_options(self):
        fw_group = ['firewall', 'group']
        self.cli_set(fw_group + ['network-group', 'smoketest_net', 'network', '10.10.0.0/16'])
        self.cli_set(fw_group + ['port-group', 'smoketest_port', 'port', '5060'])
        self.cli_set(fw_group + ['mac-group', 'smoketest_mac', 'mac-address', '00:00:5e:00:53:01'])

        # translation prefix with port range and no source address to map from
        self.cli_set(src_path + ['rule', '10', 'outbound-interface', 'name', 'eth0'])
        self.cli_set(src_path + ['rule', '10', 'protocol', 'tcp'])
        self.cli_set(src_path + ['rule', '10', 'translation', 'address', '203.0.113.0/24'])
        self.cli_set(src_path + ['rule', '10', 'translation', 'port', '1025-2000'])

        self.cli_set(src_path + ['rule', '20', 'outbound-interface', 'name', '!eth1'])
        self.cli_set(src_path + ['rule', '20', 'protocol', 'udp'])
        self.cli_set(src_path + ['rule', '20', 'source', 'group', 'network-group', 'smoketest_net'])
        self.cli_set(src_path + ['rule', '20', 'translation', 'address', 'masquerade'])
        self.cli_set(src_path + ['rule', '20', 'translation', 'port', '30000-40000'])
        self.cli_set(src_path + ['rule', '20', 'log'])

        self.cli_set(src_path + ['rule', '30', 'outbound-interface', 'name', 'eth*'])
        self.cli_set(src_path + ['rule', '30', 'translation', 'address', '198.51.100.10-198.51.100.20'])
        self.cli_set(src_path + ['rule', '30', 'translation', 'options', 'address-mapping', 'persistent'])
        self.cli_set(src_path + ['rule', '30', 'translation', 'options', 'port-mapping', 'random'])

        self.cli_set(src_path + ['rule', '40', 'destination', 'address', '10.20.0.0/16'])
        self.cli_set(src_path + ['rule', '40', 'exclude'])
        self.cli_set(src_path + ['rule', '40', 'log'])

        self.cli_set(src_path + ['rule', '50', 'protocol', 'udp'])
        self.cli_set(src_path + ['rule', '50', 'source', 'group', 'port-group', 'smoketest_port'])
        self.cli_set(src_path + ['rule', '50', 'translation', 'port', '5070'])

        self.cli_set(src_path + ['rule', '60', 'source', 'group', 'mac-group', 'smoketest_mac'])
        self.cli_set(src_path + ['rule', '60', 'packet-type', 'host'])
        self.cli_set(src_path + ['rule', '60', 'translation', 'address', 'masquerade'])

        self.cli_set(src_path + ['rule', '70', 'source', 'address', '10.70.0.0/16'])
        self.cli_set(src_path + ['rule', '70', 'translation', 'address', 'masquerade'])
        self.cli_set(src_path + ['rule', '70', 'disable'])

        out = self.cli_commit()
        # a wildcard is not an interface name that can be looked up
        self.assertNotIn('does not exist', out)

        nftables_search = [
            ['oifname "eth0"', 'meta l4proto tcp', 'snat ip prefix to ip saddr map { 0.0.0.0/0 : 203.0.113.0/24 . 1025-2000 }', 'comment "SRC-NAT-10"'],
            ['oifname != "eth1"', 'meta l4proto udp', 'ip saddr @N_smoketest_net', 'log prefix "[SRC-NAT-20-MASQ]"', 'masquerade to :30000-40000', 'comment "SRC-NAT-20"'],
            ['oifname "eth*"', 'snat to 198.51.100.10-198.51.100.20 random,persistent', 'comment "SRC-NAT-30"'],
            ['ip daddr 10.20.0.0/16', 'log prefix "[SRC-NAT-40-EXCL]"', 'return', 'comment "SRC-NAT-40"'],
            ['udp sport @P_smoketest_port', 'snat to :5070', 'comment "SRC-NAT-50"'],
            ['meta pkttype host', 'ether saddr @M_smoketest_mac', 'masquerade', 'comment "SRC-NAT-60"'],
        ]
        self.verify_nftables(nftables_search, 'ip vyos_nat')
        self.verify_nftables([['10.70.0.0/16'], ['SRC-NAT-70']], 'ip vyos_nat', inverse=True)

        self.cli_delete(['firewall'])

    def test_dnat_options(self):
        fw_group = ['firewall', 'group']
        self.cli_set(fw_group + ['interface-group', 'smoketest_ifaces', 'interface', 'eth0'])
        self.cli_set(fw_group + ['network-group', 'smoketest_net', 'network', '198.51.100.0/24'])

        # prefix to prefix map
        self.cli_set(dst_path + ['rule', '10', 'inbound-interface', 'group', 'smoketest_ifaces'])
        self.cli_set(dst_path + ['rule', '10', 'destination', 'address', '203.0.113.0/24'])
        self.cli_set(dst_path + ['rule', '10', 'translation', 'address', '10.0.0.0/24'])

        self.cli_set(dst_path + ['rule', '20', 'inbound-interface', 'name', 'eth0'])
        self.cli_set(dst_path + ['rule', '20', 'protocol', 'tcp'])
        self.cli_set(dst_path + ['rule', '20', 'destination', 'port', '80'])
        self.cli_set(dst_path + ['rule', '20', 'translation', 'address', '10.1.0.0/24'])
        self.cli_set(dst_path + ['rule', '20', 'translation', 'port', '8080'])

        self.cli_set(dst_path + ['rule', '30', 'source', 'group', 'network-group', 'smoketest_net'])
        self.cli_set(dst_path + ['rule', '30', 'exclude'])
        self.cli_set(dst_path + ['rule', '30', 'log'])

        self.cli_set(dst_path + ['rule', '40', 'inbound-interface', 'name', '!eth1'])
        self.cli_set(dst_path + ['rule', '40', 'protocol', 'tcp_udp'])
        self.cli_set(dst_path + ['rule', '40', 'destination', 'port', '!53'])
        self.cli_set(dst_path + ['rule', '40', 'translation', 'address', '192.0.2.40'])
        self.cli_set(dst_path + ['rule', '40', 'translation', 'options', 'address-mapping', 'persistent'])

        self.cli_commit()

        nftables_search = [
            ['iifname @I_smoketest_ifaces', 'dnat ip prefix to ip daddr map { 203.0.113.0/24 : 10.0.0.0/24 }', 'comment "DST-NAT-10"'],
            ['iifname "eth0"', 'tcp dport 80', 'dnat ip prefix to ip daddr map { 0.0.0.0/0 : 10.1.0.0/24 . 8080 }', 'comment "DST-NAT-20"'],
            ['ip saddr @N_smoketest_net', 'log prefix "[DST-NAT-30-EXCL]"', 'return', 'comment "DST-NAT-30"'],
            ['iifname != "eth1"', 'meta l4proto { tcp, udp }', 'th dport != 53', 'dnat to 192.0.2.40 persistent', 'comment "DST-NAT-40"'],
        ]
        self.verify_nftables(nftables_search, 'ip vyos_nat')

        self.cli_delete(['firewall'])

    def test_nat_verify(self):
        rule = src_path + ['rule', '10']
        self.cli_set(rule + ['translation', 'address', 'masquerade'])

        # a missing mac-group must be caught like the other group types
        self.cli_set(rule + ['source', 'group', 'mac-group', 'smoketest_mac'])
        self.assert_commit_fails('Invalid mac-group "smoketest_mac" on nat rule')

        self.cli_set(['firewall', 'group', 'mac-group', 'smoketest_mac', 'mac-address', '00:00:5e:00:53:01'])
        self.cli_commit()
        self.verify_nftables([['ether saddr @M_smoketest_mac', 'masquerade', 'comment "SRC-NAT-10"']], 'ip vyos_nat')

        self.cli_set(rule + ['destination', 'group', 'address-group', 'smoketest_addr'])
        self.assert_commit_fails('Invalid address-group "smoketest_addr" on nat rule')
        self.cli_delete(rule + ['destination'])

        self.cli_set(rule + ['destination', 'port', '443'])
        self.assert_commit_fails('ports can only be specified when protocol is either tcp, udp or tcp_udp')
        self.cli_delete(rule + ['destination'])

        self.cli_set(rule + ['outbound-interface', 'name', 'eth0'])
        self.cli_set(rule + ['outbound-interface', 'group', 'smoketest_ifaces'])
        self.assert_commit_fails('cannot specify both interface group and interface name')
        self.cli_delete(rule + ['outbound-interface'])

        self.cli_delete(rule + ['translation'])
        self.cli_set(rule + ['protocol', 'tcp_udp'])
        self.cli_set(rule + ['load-balance', 'hash', 'source-port'])
        self.cli_set(rule + ['load-balance', 'backend', '203.0.113.1', 'weight', '100'])
        self.assert_commit_fails('Protocol must be tcp or udp when specifying hash ports')
        self.cli_delete(rule)

        self.cli_set(static_path + ['rule', '10', 'destination', 'address', '203.0.113.5'])
        self.cli_set(static_path + ['rule', '10', 'translation', 'address', '10.0.0.5'])
        self.assert_commit_fails('inbound-interface not specified')

        self.cli_discard()
        self.cli_delete(['firewall'])

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
