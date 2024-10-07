#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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

interface = 'eth0'
mark = '100'
table_id = '101'
extra_table_id = '102'
vrf_name = 'LPBRVRF'
vrf_rt_id = '202'

class TestPolicyLocalRoute(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestPolicyLocalRoute, cls).setUpClass()
        # Clear out current configuration to allow running this test on a live system
        cls.cli_delete(cls, ['policy', 'local-route'])
        cls.cli_delete(cls, ['policy', 'local-route6'])

        cls.cli_set(cls, ['vrf', 'name', vrf_name, 'table', vrf_rt_id])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['vrf', 'name', vrf_name])

        super(TestPolicyLocalRoute, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(['policy', 'local-route'])
        self.cli_delete(['policy', 'local-route6'])
        self.cli_commit()

        ip_rule_search = [
            [f'lookup {table_id}']
        ]

        self.verify_rules(ip_rule_search, inverse=True)
        self.verify_rules(ip_rule_search, inverse=True, addr_family='inet6')

    def test_local_pbr_matching_criteria(self):
        self.cli_set(['policy', 'local-route', 'rule', '4', 'inbound-interface', interface])
        self.cli_set(['policy', 'local-route', 'rule', '4', 'protocol', 'udp'])
        self.cli_set(['policy', 'local-route', 'rule', '4', 'fwmark', mark])
        self.cli_set(['policy', 'local-route', 'rule', '4', 'destination', 'address', '198.51.100.0/24'])
        self.cli_set(['policy', 'local-route', 'rule', '4', 'destination', 'port', '111'])
        self.cli_set(['policy', 'local-route', 'rule', '4', 'source', 'address', '198.51.100.1'])
        self.cli_set(['policy', 'local-route', 'rule', '4', 'source', 'port', '443'])
        self.cli_set(['policy', 'local-route', 'rule', '4', 'set', 'table', table_id])

        self.cli_set(['policy', 'local-route6', 'rule', '6', 'inbound-interface', interface])
        self.cli_set(['policy', 'local-route6', 'rule', '6', 'protocol', 'tcp'])
        self.cli_set(['policy', 'local-route6', 'rule', '6', 'fwmark', mark])
        self.cli_set(['policy', 'local-route6', 'rule', '6', 'destination', 'address', '2001:db8::/64'])
        self.cli_set(['policy', 'local-route6', 'rule', '6', 'destination', 'port', '123'])
        self.cli_set(['policy', 'local-route6', 'rule', '6', 'source', 'address', '2001:db8::1'])
        self.cli_set(['policy', 'local-route6', 'rule', '6', 'source', 'port', '80'])
        self.cli_set(['policy', 'local-route6', 'rule', '6', 'set', 'table', table_id])

        self.cli_commit()

        rule_lookup = f'lookup {table_id}'
        rule_fwmark = 'fwmark ' + hex(int(mark))
        rule_interface = f'iif {interface}'

        ip4_rule_search = [
            ['from 198.51.100.1', 'to 198.51.100.0/24', rule_fwmark, rule_interface, 'ipproto udp', 'sport 443', 'dport 111', rule_lookup]
        ]

        self.verify_rules(ip4_rule_search)

        ip6_rule_search = [
            ['from 2001:db8::1', 'to 2001:db8::/64', rule_fwmark, rule_interface, 'ipproto tcp', 'sport 80', 'dport 123', rule_lookup]
        ]

        self.verify_rules(ip6_rule_search, addr_family='inet6')

    def test_local_pbr_rule_removal(self):
        self.cli_set(['policy', 'local-route', 'rule', '1', 'destination', 'address', '198.51.100.1'])
        self.cli_set(['policy', 'local-route', 'rule', '1', 'set', 'table', table_id])

        self.cli_set(['policy', 'local-route', 'rule', '2', 'destination', 'address', '198.51.100.2'])
        self.cli_set(['policy', 'local-route', 'rule', '2', 'set', 'table', table_id])

        self.cli_set(['policy', 'local-route', 'rule', '3', 'destination', 'address', '198.51.100.3'])
        self.cli_set(['policy', 'local-route', 'rule', '3', 'set', 'table', table_id])

        self.cli_commit()

        rule_lookup = f'lookup {table_id}'

        ip_rule_search = [
            ['to 198.51.100.1', rule_lookup],
            ['to 198.51.100.2', rule_lookup],
            ['to 198.51.100.3', rule_lookup],
        ]

        self.verify_rules(ip_rule_search)

        self.cli_delete(['policy', 'local-route', 'rule', '2'])
        self.cli_commit()

        ip_rule_missing = [
            ['to 198.51.100.2', rule_lookup],
        ]

        self.verify_rules(ip_rule_missing, inverse=True)

    def test_local_pbr_rule_changes(self):
        self.cli_set(['policy', 'local-route', 'rule', '1', 'destination', 'address', '198.51.100.0/24'])
        self.cli_set(['policy', 'local-route', 'rule', '1', 'set', 'table', table_id])

        self.cli_commit()

        self.cli_set(['policy', 'local-route', 'rule', '1', 'set', 'table', extra_table_id])
        self.cli_commit()

        ip_rule_search_extra = [
            ['to 198.51.100.0/24', f'lookup {extra_table_id}']
        ]

        self.verify_rules(ip_rule_search_extra)

        ip_rule_search_orig = [
            ['to 198.51.100.0/24', f'lookup {table_id}']
        ]

        self.verify_rules(ip_rule_search_orig, inverse=True)

        self.cli_delete(['policy', 'local-route', 'rule', '1', 'set', 'table'])
        self.cli_set(['policy', 'local-route', 'rule', '1', 'set', 'vrf', vrf_name])

        self.cli_commit()

        ip_rule_search_vrf = [
            ['to 198.51.100.0/24', f'lookup {vrf_name}']
        ]

        self.verify_rules(ip_rule_search_extra, inverse=True)
        self.verify_rules(ip_rule_search_vrf)

    def test_local_pbr_target_vrf(self):
        self.cli_set(['policy', 'local-route', 'rule', '1', 'destination', 'address', '198.51.100.0/24'])
        self.cli_set(['policy', 'local-route', 'rule', '1', 'set', 'vrf', vrf_name])

        self.cli_commit()

        ip_rule_search = [
            ['to 198.51.100.0/24', f'lookup {vrf_name}']
        ]

        self.verify_rules(ip_rule_search)


if __name__ == '__main__':
    unittest.main(verbosity=2)
