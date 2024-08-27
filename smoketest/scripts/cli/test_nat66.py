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

import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError

base_path = ['nat66']
src_path = base_path + ['source']
dst_path = base_path + ['destination']

class TestNAT66(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestNAT66, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_source_nat66(self):
        source_prefix = 'fc00::/64'
        translation_prefix = 'fc01::/64'
        self.cli_set(src_path + ['rule', '1', 'outbound-interface', 'name', 'eth1'])
        self.cli_set(src_path + ['rule', '1', 'source', 'prefix', source_prefix])
        self.cli_set(src_path + ['rule', '1', 'translation', 'address', translation_prefix])

        self.cli_set(src_path + ['rule', '2', 'outbound-interface', 'name', 'eth1'])
        self.cli_set(src_path + ['rule', '2', 'source', 'prefix', source_prefix])
        self.cli_set(src_path + ['rule', '2', 'translation', 'address', 'masquerade'])

        self.cli_set(src_path + ['rule', '3', 'outbound-interface', 'name', 'eth1'])
        self.cli_set(src_path + ['rule', '3', 'source', 'prefix', source_prefix])
        self.cli_set(src_path + ['rule', '3', 'exclude'])

        self.cli_commit()

        nftables_search = [
            ['oifname "eth1"', f'ip6 saddr {source_prefix}', f'snat prefix to {translation_prefix}'],
            ['oifname "eth1"', f'ip6 saddr {source_prefix}', 'masquerade'],
            ['oifname "eth1"', f'ip6 saddr {source_prefix}', 'return']
        ]

        self.verify_nftables(nftables_search, 'ip6 vyos_nat')

    def test_source_nat66_address(self):
        source_prefix = 'fc00::/64'
        translation_address = 'fc00::1'
        self.cli_set(src_path + ['rule', '1', 'outbound-interface', 'name', 'eth1'])
        self.cli_set(src_path + ['rule', '1', 'source', 'prefix', source_prefix])
        self.cli_set(src_path + ['rule', '1', 'translation', 'address', translation_address])

        # check validate() - outbound-interface must be defined
        self.cli_commit()

        nftables_search = [
            ['oifname "eth1"', f'ip6 saddr {source_prefix}', f'snat to {translation_address}']
        ]

        self.verify_nftables(nftables_search, 'ip6 vyos_nat')

    def test_destination_nat66(self):
        destination_address = 'fc00::1'
        translation_address = 'fc01::1'
        source_address = 'fc02::1'
        self.cli_set(dst_path + ['rule', '1', 'inbound-interface', 'name', 'eth1'])
        self.cli_set(dst_path + ['rule', '1', 'destination', 'address', destination_address])
        self.cli_set(dst_path + ['rule', '1', 'translation', 'address', translation_address])

        self.cli_set(dst_path + ['rule', '2', 'inbound-interface', 'name', 'eth1'])
        self.cli_set(dst_path + ['rule', '2', 'destination', 'address', destination_address])
        self.cli_set(dst_path + ['rule', '2', 'source', 'address', source_address])
        self.cli_set(dst_path + ['rule', '2', 'exclude'])

        # check validate() - outbound-interface must be defined
        self.cli_commit()

        nftables_search = [
            ['iifname "eth1"', 'ip6 daddr fc00::1', 'dnat to fc01::1'],
            ['iifname "eth1"', 'ip6 saddr fc02::1', 'ip6 daddr fc00::1', 'return']
        ]

        self.verify_nftables(nftables_search, 'ip6 vyos_nat')

    def test_destination_nat66_protocol(self):
        translation_address = '2001:db8:1111::1'
        source_prefix = '2001:db8:2222::/64'
        dport = '4545'
        sport = '8080'
        tport = '5555'
        proto = 'tcp'
        self.cli_set(dst_path + ['rule', '1', 'inbound-interface', 'name', 'eth1'])
        self.cli_set(dst_path + ['rule', '1', 'destination', 'port', dport])
        self.cli_set(dst_path + ['rule', '1', 'source', 'address', source_prefix])
        self.cli_set(dst_path + ['rule', '1', 'source', 'port', sport])
        self.cli_set(dst_path + ['rule', '1', 'protocol', proto])
        self.cli_set(dst_path + ['rule', '1', 'translation', 'address', translation_address])
        self.cli_set(dst_path + ['rule', '1', 'translation', 'port', tport])

        # check validate() - outbound-interface must be defined
        self.cli_commit()

        nftables_search = [
            ['iifname "eth1"', 'tcp dport 4545', 'ip6 saddr 2001:db8:2222::/64', 'tcp sport 8080', 'dnat to [2001:db8:1111::1]:5555']
        ]

        self.verify_nftables(nftables_search, 'ip6 vyos_nat')

    def test_destination_nat66_prefix(self):
        destination_prefix = 'fc00::/64'
        translation_prefix = 'fc01::/64'
        self.cli_set(dst_path + ['rule', '1', 'inbound-interface', 'name', 'eth1'])
        self.cli_set(dst_path + ['rule', '1', 'destination', 'address', destination_prefix])
        self.cli_set(dst_path + ['rule', '1', 'translation', 'address', translation_prefix])

        # check validate() - outbound-interface must be defined
        self.cli_commit()

        nftables_search = [
            ['iifname "eth1"', f'ip6 daddr {destination_prefix}', f'dnat prefix to {translation_prefix}']
        ]

        self.verify_nftables(nftables_search, 'ip6 vyos_nat')

    def test_destination_nat66_network_group(self):
        address_group = 'smoketest_addr'
        address_group_member = 'fc00::1'
        network_group = 'smoketest_net'
        network_group_member = 'fc00::/64'
        translation_prefix = 'fc01::/64'

        self.cli_set(['firewall', 'group', 'ipv6-address-group', address_group, 'address', address_group_member])
        self.cli_set(['firewall', 'group', 'ipv6-network-group', network_group, 'network', network_group_member])

        self.cli_set(dst_path + ['rule', '1', 'destination', 'group', 'address-group', address_group])
        self.cli_set(dst_path + ['rule', '1', 'translation', 'address', translation_prefix])

        self.cli_set(dst_path + ['rule', '2', 'destination', 'group', 'network-group', network_group])
        self.cli_set(dst_path + ['rule', '2', 'translation', 'address', translation_prefix])

        self.cli_commit()

        nftables_search = [
            [f'set A6_{address_group}'],
            [f'elements = {{ {address_group_member} }}'],
            [f'set N6_{network_group}'],
            [f'elements = {{ {network_group_member} }}'],
            ['ip6 daddr', f'@A6_{address_group}', 'dnat prefix to fc01::/64'],
            ['ip6 daddr', f'@N6_{network_group}', 'dnat prefix to fc01::/64']
        ]

        self.verify_nftables(nftables_search, 'ip6 vyos_nat')


    def test_destination_nat66_without_translation_address(self):
        self.cli_set(dst_path + ['rule', '1', 'inbound-interface', 'name', 'eth1'])
        self.cli_set(dst_path + ['rule', '1', 'destination', 'port', '443'])
        self.cli_set(dst_path + ['rule', '1', 'protocol', 'tcp'])
        self.cli_set(dst_path + ['rule', '1', 'translation', 'port', '443'])

        self.cli_commit()

        nftables_search = [
            ['iifname "eth1"', 'tcp dport 443', 'dnat to :443']
        ]

        self.verify_nftables(nftables_search, 'ip6 vyos_nat')

    def test_source_nat66_required_translation_prefix(self):
        # T2813: Ensure translation address is specified
        rule = '5'
        source_prefix = 'fc00::/64'
        self.cli_set(src_path + ['rule', rule, 'source', 'prefix', source_prefix])

        # check validate() - outbound-interface must be defined
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(src_path + ['rule', rule, 'outbound-interface', 'name', 'eth0'])

        # check validate() - translation address not specified
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(src_path + ['rule', rule, 'translation', 'address', 'masquerade'])
        self.cli_commit()

    def test_source_nat66_protocol(self):
        translation_address = '2001:db8:1111::1'
        source_prefix = '2001:db8:2222::/64'
        dport = '9999'
        sport = '8080'
        tport = '80'
        proto = 'tcp'
        self.cli_set(src_path + ['rule', '1', 'outbound-interface', 'name', 'eth1'])
        self.cli_set(src_path + ['rule', '1', 'destination', 'port', dport])
        self.cli_set(src_path + ['rule', '1', 'source', 'prefix', source_prefix])
        self.cli_set(src_path + ['rule', '1', 'source', 'port', sport])
        self.cli_set(src_path + ['rule', '1', 'protocol', proto])
        self.cli_set(src_path + ['rule', '1', 'translation', 'address', translation_address])
        self.cli_set(src_path + ['rule', '1', 'translation', 'port', tport])

        # check validate() - outbound-interface must be defined
        self.cli_commit()

        nftables_search = [
            ['oifname "eth1"', 'ip6 saddr 2001:db8:2222::/64', 'tcp dport 9999', 'tcp sport 8080', 'snat to [2001:db8:1111::1]:80']
        ]

        self.verify_nftables(nftables_search, 'ip6 vyos_nat')

    def test_nat66_no_rules(self):
        # T3206: deleting all rules but keep the direction 'destination' or
        # 'source' resulteds in KeyError: 'rule'.
        #
        # Test that both 'nat destination' and 'nat source' nodes can exist
        # without any rule
        self.cli_set(src_path)
        self.cli_set(dst_path)
        self.cli_commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
