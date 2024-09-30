#!/usr/bin/env python3
#
# Copyright (C) 2020-2024 VyOS maintainers and contributors
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
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.configsession import ConfigSessionError

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
        interface_group_member = 'bond.99'

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
                rule_search.append(f'iifname "{inbound_iface_200}"')

            nftables_search.append(rule_search)

        self.cli_commit()

        self.verify_nftables(nftables_search, 'ip vyos_nat')

    def test_snat_required_translation_address(self):
        # T2813: Ensure translation address is specified
        rule = '5'
        self.cli_set(src_path + ['rule', rule, 'source', 'address', '192.0.2.0/24'])

        # check validate() - translation address not specified
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

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

        self.cli_commit()

        nftables_search = [
            [f'iifname "{ifname}"', f'ip daddr {dst_addr_1}', f'dnat to {translate_addr_1}'],
            [f'oifname "{ifname}"', f'ip saddr {translate_addr_1}', f'snat to {dst_addr_1}'],
            [f'iifname "{ifname}"', f'dnat ip prefix to ip daddr map {{ {dst_addr_2} : {translate_addr_2} }}'],
            [f'oifname "{ifname}"', f'snat ip prefix to ip saddr map {{ {translate_addr_2} : {dst_addr_2} }}']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_static_nat')

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

        self.cli_commit()

        nftables_search = [
            [f'iifname "{ifname}"', f'tcp dport {dst_port}', f'dnat to jhash ip saddr . tcp sport . ip daddr . tcp dport mod 100 map', f'0-9 : {member_1}, 10-99 : {member_2}'],
            [f'oifname "{ifname}"', f'snat to numgen random mod 100 map', f'0-34 : {member_3}, 35-99 : {member_4}']
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
        destination_domain = 'vyos.io'

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
if __name__ == '__main__':
    unittest.main(verbosity=2)
