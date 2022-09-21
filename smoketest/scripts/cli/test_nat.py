#!/usr/bin/env python3
#
# Copyright (C) 2020-2022 VyOS maintainers and contributors
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

import jmespath
import json
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.configsession import ConfigSessionError
from vyos.util import cmd
from vyos.util import dict_search

base_path = ['nat']
src_path = base_path + ['source']
dst_path = base_path + ['destination']
static_path = base_path + ['static']

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

    def verify_nftables(self, nftables_search, table, inverse=False, args=''):
        nftables_output = cmd(f'sudo nft {args} list table {table}')

        for search in nftables_search:
            matched = False
            for line in nftables_output.split("\n"):
                if all(item in line for item in search):
                    matched = True
                    break
            self.assertTrue(not matched if inverse else matched, msg=search)

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
                self.cli_set(src_path + ['rule', rule, 'outbound-interface', outbound_iface_100])
                self.cli_set(src_path + ['rule', rule, 'translation', 'address', 'masquerade'])
                nftables_search.append([f'saddr {network}', f'oifname "{outbound_iface_100}"', 'masquerade'])
            else:
                self.cli_set(src_path + ['rule', rule, 'destination', 'address', network])
                self.cli_set(src_path + ['rule', rule, 'outbound-interface', outbound_iface_200])
                self.cli_set(src_path + ['rule', rule, 'exclude'])
                nftables_search.append([f'daddr {network}', f'oifname "{outbound_iface_200}"', 'return'])

        self.cli_commit()

        self.verify_nftables(nftables_search, 'ip vyos_nat')

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
                self.cli_set(dst_path + ['rule', rule, 'inbound-interface', inbound_iface_100])
                rule_search.append(f'{inbound_proto_100} sport {port}')
                rule_search.append(f'iifname "{inbound_iface_100}"')
            else:
                self.cli_set(dst_path + ['rule', rule, 'protocol', inbound_proto_200])
                self.cli_set(dst_path + ['rule', rule, 'inbound-interface', inbound_iface_200])
                rule_search.append(f'iifname "{inbound_iface_200}"')

            nftables_search.append(rule_search)

        self.cli_commit()

        self.verify_nftables(nftables_search, 'ip vyos_nat')

    def test_snat_required_translation_address(self):
        # T2813: Ensure translation address is specified
        rule = '5'
        self.cli_set(src_path + ['rule', rule, 'source', 'address', '192.0.2.0/24'])

        # check validate() - outbound-interface must be defined
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(src_path + ['rule', rule, 'outbound-interface', 'eth0'])

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
        self.cli_set(dst_path + ['rule', rule, 'inbound-interface', 'eth0'])
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
        self.cli_set(dst_path + ['rule', '1', 'inbound-interface', 'eth1'])
        self.cli_set(dst_path + ['rule', '1', 'destination', 'port', '443'])
        self.cli_set(dst_path + ['rule', '1', 'protocol', 'tcp'])
        self.cli_set(dst_path + ['rule', '1', 'translation', 'port', '443'])

        self.cli_commit()

        nftables_search = [
            ['iifname "eth1"', 'tcp dport 443', 'dnat to :443']
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

if __name__ == '__main__':
    unittest.main(verbosity=2)
