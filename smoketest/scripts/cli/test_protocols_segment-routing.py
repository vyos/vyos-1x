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

import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Section
from vyos.frrender import zebra_daemon
from vyos.utils.process import process_named_running
from vyos.utils.system import sysctl_read

base_path = ['protocols', 'segment-routing']

class TestProtocolsSegmentRouting(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        # call base-classes classmethod
        super(TestProtocolsSegmentRouting, cls).setUpClass()
        # Retrieve FRR daemon PID - it is not allowed to crash, thus PID must remain the same
        cls.daemon_pid = process_named_running(zebra_daemon)
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)
        # create a VLAN interface for testing
        cls.cli_set(cls, ['interfaces', 'ethernet', 'eth0', 'vif', '4000',
                          'address', '192.168.40.1/24'])
        cls.cli_commit(cls)
        cls._interfaces = Section.interfaces('ethernet', vlan=True)

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['interfaces', 'ethernet', 'eth0', 'vif', '4000'])
        super(TestProtocolsSegmentRouting, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        # check process health and continuity
        self.assertEqual(self.daemon_pid, process_named_running(zebra_daemon))
        # always forward to base class
        super().tearDown()

    def test_srv6(self):
        locators = {
            'foo1': {'prefix': '2001:a::/64'},
            'foo2': {'prefix': '2001:b::/64', 'usid': {}},
            'foo3': {'prefix': '2001:c::/64', 'format': 'uncompressed-f4024'},
            'foo4': {
                'prefix': '2001:d::/48',
                'block-len': '32',
                'node-len': '16',
                'func-bits': '12',
                'usid': {},
                'format': 'usid-f3216',
            },
        }

        for locator, locator_config in locators.items():
            self.cli_set(
                base_path
                + ['srv6', 'locator', locator, 'prefix', locator_config['prefix']]
            )
            if 'block-len' in locator_config:
                self.cli_set(
                    base_path
                    + [
                        'srv6',
                        'locator',
                        locator,
                        'block-len',
                        locator_config['block-len'],
                    ]
                )
            if 'node-len' in locator_config:
                self.cli_set(
                    base_path
                    + [
                        'srv6',
                        'locator',
                        locator,
                        'node-len',
                        locator_config['node-len'],
                    ]
                )
            if 'func-bits' in locator_config:
                self.cli_set(
                    base_path
                    + [
                        'srv6',
                        'locator',
                        locator,
                        'func-bits',
                        locator_config['func-bits'],
                    ]
                )
            if 'usid' in locator_config:
                self.cli_set(base_path + ['srv6', 'locator', locator, 'behavior-usid'])
            if 'format' in locator_config:
                self.cli_set(
                    base_path
                    + ['srv6', 'locator', locator, 'format', locator_config['format']]
                )

        # verify() - SRv6 should be enabled on at least one interface!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for interface in self._interfaces:
            self.cli_set(base_path + ['interface', interface, 'srv6'])

        self.cli_commit()

        for interface in self._interfaces:
            self.assertEqual(
                sysctl_read(['net', 'ipv6', 'conf', interface, 'seg6_enabled']), '1'
            )
            self.assertEqual(
                sysctl_read(['net', 'ipv6', 'conf', interface, 'seg6_require_hmac']), '0'
            )  # default

        frrconfig = self.getFRRconfig('segment-routing', stop_section='^exit')
        self.assertIn('segment-routing', frrconfig)
        self.assertIn(' srv6', frrconfig)
        self.assertIn('  locators', frrconfig)
        for locator, locator_config in locators.items():
            prefix = locator_config['prefix']
            block_len = (
                f' block-len {locator_config["block-len"]}'
                if 'block-len' in locator_config
                else ''
            )
            node_len = (
                f' node-len {locator_config["node-len"]}'
                if 'node-len' in locator_config
                else ''
            )
            func_bits = (
                f' func-bits {locator_config["func-bits"]}'
                if 'func-bits' in locator_config
                else ''
            )

            self.assertIn(f'   locator {locator}', frrconfig)
            self.assertIn(
                f'    prefix {prefix}{block_len}{node_len}{func_bits}',
                frrconfig,
            )

            if 'format' in locator_config:
                self.assertIn(f'    format {locator_config["format"]}', frrconfig)
            if 'usid' in locator_config:
                self.assertIn('    behavior usid', frrconfig)

    def test_srv6_encap_source_addr(self):
        # Set an IPv6 address for SRv6 encapsulation source
        source6 = '2001:db8::1'

        # SRv6 must be enabled on at least one interface
        for interface in self._interfaces:
            self.cli_set(base_path + ['interface', interface, 'srv6'])

        self.cli_set(base_path + ['srv6', 'encapsulation', 'source-address', source6])
        self.cli_commit()

        frrconfig = self.getFRRconfig('segment-routing', stop_section='^exit')
        self.assertIn('segment-routing', frrconfig)
        self.assertIn(' srv6', frrconfig)
        self.assertIn('  encapsulation', frrconfig)
        self.assertIn(f'   source-address {source6}', frrconfig)

    def test_srv6_sysctl(self):

        # HMAC accept
        for interface in self._interfaces:
            self.cli_set(base_path + ['interface', interface, 'srv6'])
            self.cli_set(base_path + ['interface', interface, 'srv6', 'hmac', 'ignore'])
        self.cli_commit()

        for interface in self._interfaces:
            self.assertEqual(
                sysctl_read(['net', 'ipv6', 'conf', interface, 'seg6_enabled']), '1'
            )
            self.assertEqual(
                sysctl_read(['net', 'ipv6', 'conf', interface, 'seg6_require_hmac']), '-1'
            )  # ignore

        # HMAC drop
        for interface in self._interfaces:
            self.cli_set(base_path + ['interface', interface, 'srv6'])
            self.cli_set(base_path + ['interface', interface, 'srv6', 'hmac', 'drop'])
        self.cli_commit()

        for interface in self._interfaces:
            self.assertEqual(
                sysctl_read(['net', 'ipv6', 'conf', interface, 'seg6_enabled']), '1'
            )
            self.assertEqual(
                sysctl_read(['net', 'ipv6', 'conf', interface, 'seg6_require_hmac']), '1'
            )  # drop

        # Disable SRv6 on first interface
        first_if = self._interfaces[-1]
        self.cli_delete(base_path + ['interface', first_if])
        self.cli_commit()

        self.assertEqual(sysctl_read(['net', 'ipv6', 'conf', first_if, 'seg6_enabled']), '0')

    def test_srte_database(self):
        for protocol in ['isis', 'ospf']:
            self.cli_set(base_path + ['traffic-engineering', 'database-import-protocol', protocol])
        # IS-IS and OSPF are mutually exclusive
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # Add database-import-protocol for isis and check the config
        for protocol in ['isis', 'ospf']:
            self.cli_delete(base_path)
            self.cli_set(base_path + ['traffic-engineering', 'database-import-protocol', protocol])
            self.cli_commit()

            frrconfig = self.getFRRconfig(f'segment-routing', stop_section='^exit')
            self.assertIn('segment-routing', frrconfig)
            self.assertIn(' traffic-eng', frrconfig)
            self.assertIn('  mpls-te on', frrconfig)
            self.assertIn(f'  mpls-te import {protocol}', frrconfig)

    def test_srte_mpls_label(self):
        # Add segment-list with an mpls value
        mpls_label = '500'
        segment_list = 'smoketest-mpls-only-segment-list'
        index_value = '0'

        self.cli_set(base_path + ['traffic-engineering', 'segment-list', segment_list,
                                  'index', index_value, 'mpls', 'label', mpls_label])
        self.cli_commit()

        frrconfig = self.getFRRconfig(f'segment-routing', stop_section='^exit')
        self.assertIn('segment-routing', frrconfig)
        self.assertIn(' traffic-eng', frrconfig)
        self.assertIn('  mpls-te on', frrconfig)
        self.assertIn(f'  segment-list {segment_list}', frrconfig)
        self.assertIn(f'   index {index_value} mpls label {mpls_label}', frrconfig)

    def test_srte_mpls_label_and_adjacency(self):
        # Add segment-list with an mpls value and adjacency
        mpls_label = '1000'
        segment_list = 'smoketest-mpls-with-adjacency-segment-list'
        index_value = '0'

        addresses = {'ipv4' : {'source_identifier' : '192.168.255.1', 'destination_identifier' : '192.168.255.2'},
                     'ipv6' : {'source_identifier' : '2003::1', 'destination_identifier' : '2003::2'}}

        test_path = base_path + ['traffic-engineering', 'segment-list', segment_list, 'index', index_value]
        for address_family in ['ipv4', 'ipv6']:
            source_identifier = addresses[address_family]['source_identifier']
            destination_identifier = addresses[address_family]['destination_identifier']
            # Make testcase re-entrant for next for loop
            self.cli_delete(test_path)

            self.cli_set(test_path + ['mpls', 'label', mpls_label])
            self.cli_set(test_path + ['nai', 'adjacency', address_family, 'source-identifier', source_identifier])
            self.cli_set(test_path + ['nai', 'adjacency', address_family, 'destination-identifier', destination_identifier])
            self.cli_commit()

            frrconfig = self.getFRRconfig(f'segment-routing', stop_section='^exit')
            self.assertIn(f'segment-routing', frrconfig)
            self.assertIn(f' traffic-eng', frrconfig)
            self.assertIn(f'  mpls-te on', frrconfig)
            self.assertIn(f'  segment-list {segment_list}', frrconfig)
            self.assertIn(f'   index {index_value} mpls label {mpls_label}', frrconfig)
            self.assertIn(f'   index {index_value} nai adjacency {source_identifier} {destination_identifier}', frrconfig)

    def test_srte_mpls_label_and_prefix(self):
        # Add segment-list with an mpls value and prefix
        mpls_label = '1500'
        segment_list = 'smoketest-mpls-with-prefix-segment-list'
        index_value = '0'

        prefixes = {'ipv4' : {'prefix' : '192.168.255.0/24'},
                    'ipv6' : {'prefix' : '2003::/120'}}

        test_path = base_path + ['traffic-engineering', 'segment-list', segment_list, 'index', index_value]
        for address_family in ['ipv4', 'ipv6']:
            for algorithm_type in ['spf', 'strict-spf']:
                prefix = prefixes[address_family]['prefix']
                # Make testcase re-entrant for next for loop
                self.cli_delete(test_path)

                self.cli_set(test_path + ['mpls', 'label', mpls_label])
                self.cli_set(test_path + ['nai', 'prefix', address_family, 'prefix-identifier', prefix, 'algorithm', algorithm_type])
                self.cli_commit()

                frrconfig = self.getFRRconfig(f'segment-routing', stop_section='^exit')
                self.assertIn(f'segment-routing', frrconfig)
                self.assertIn(f' traffic-eng', frrconfig)
                self.assertIn(f'  mpls-te on', frrconfig)
                self.assertIn(f'  segment-list {segment_list}', frrconfig)
                if algorithm_type == 'spf':
                    self.assertIn(f'   index {index_value} mpls label {mpls_label}', frrconfig)
                    self.assertIn(f'   index {index_value} nai prefix {prefix} algorithm 0', frrconfig)
                elif algorithm_type == 'strict-spf':
                    self.assertIn(f'   index {index_value} mpls label {mpls_label}', frrconfig)
                    self.assertIn(f'   index {index_value} nai prefix {prefix} algorithm 1', frrconfig)

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
