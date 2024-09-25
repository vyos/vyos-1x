#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
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
from vyos.utils.process import process_named_running
from vyos.utils.system import sysctl_read

base_path = ['protocols', 'segment-routing']
PROCESS_NAME = 'zebra'

class TestProtocolsSegmentRouting(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        # call base-classes classmethod
        super(TestProtocolsSegmentRouting, cls).setUpClass()
        # Retrieve FRR daemon PID - it is not allowed to crash, thus PID must remain the same
        cls.daemon_pid = process_named_running(PROCESS_NAME)
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        # check process health and continuity
        self.assertEqual(self.daemon_pid, process_named_running(PROCESS_NAME))

    def test_segment_routing_01_srv6(self):
        interfaces = Section.interfaces('ethernet', vlan=False)
        locators = {
            'foo' : { 'prefix' : '2001:a::/64' },
            'foo' : { 'prefix' : '2001:b::/64', 'usid' : {} },
        }

        for locator, locator_config in locators.items():
            self.cli_set(base_path + ['srv6', 'locator', locator, 'prefix', locator_config['prefix']])
            if 'usid' in locator_config:
                self.cli_set(base_path + ['srv6', 'locator', locator, 'behavior-usid'])

        # verify() - SRv6 should be enabled on at least one interface!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface, 'srv6'])

        self.cli_commit()

        for interface in interfaces:
            self.assertEqual(sysctl_read(f'net.ipv6.conf.{interface}.seg6_enabled'), '1')
            self.assertEqual(sysctl_read(f'net.ipv6.conf.{interface}.seg6_require_hmac'), '0') # default

        frrconfig = self.getFRRconfig(f'segment-routing', daemon='zebra')
        self.assertIn(f'segment-routing', frrconfig)
        self.assertIn(f' srv6', frrconfig)
        self.assertIn(f'  locators', frrconfig)
        for locator, locator_config in locators.items():
            self.assertIn(f'   locator {locator}', frrconfig)
            self.assertIn(f'    prefix {locator_config["prefix"]} block-len 40 node-len 24 func-bits 16', frrconfig)

    def test_segment_routing_02_srv6_sysctl(self):
        interfaces = Section.interfaces('ethernet', vlan=False)

        # HMAC accept
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface, 'srv6'])
            self.cli_set(base_path + ['interface', interface, 'srv6', 'hmac', 'ignore'])
        self.cli_commit()

        for interface in interfaces:
            self.assertEqual(sysctl_read(f'net.ipv6.conf.{interface}.seg6_enabled'), '1')
            self.assertEqual(sysctl_read(f'net.ipv6.conf.{interface}.seg6_require_hmac'), '-1') # ignore

        # HMAC drop
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface, 'srv6'])
            self.cli_set(base_path + ['interface', interface, 'srv6', 'hmac', 'drop'])
        self.cli_commit()

        for interface in interfaces:
            self.assertEqual(sysctl_read(f'net.ipv6.conf.{interface}.seg6_enabled'), '1')
            self.assertEqual(sysctl_read(f'net.ipv6.conf.{interface}.seg6_require_hmac'), '1') # drop

        # Disable SRv6 on first interface
        first_if = interfaces[-1]
        self.cli_delete(base_path + ['interface', first_if])
        self.cli_commit()

        self.assertEqual(sysctl_read(f'net.ipv6.conf.{first_if}.seg6_enabled'), '0')

    def test_segment_routing_03_srte_database(self):
        # Add database-import-protocol for isis and check the config
        base_path = ['protocols', 'segment-routing', 'traffic-engineering']
        for protocol in ['isis', 'ospfv2']:
            self.cli_set(base_path + ['database-import-protocol', protocol])
            self.cli_commit()

            frrconfig = self.getFRRconfig(f'segment-routing', daemon='pathd')
            self.assertIn(f'segment-routing', frrconfig)
            self.assertIn(f' traffic-eng', frrconfig)
            self.assertIn(f'  mpls-te on', frrconfig)
            self.assertIn(f'  mpls-te import {protocol}', frrconfig)

            self.cli_delete(base_path)
            self.cli_commit()

    def test_segment_routing_04_mpls_label(self):
        # Add segment-list with an mpls value
        base_path = ['protocols', 'segment-routing', 'traffic-engineering']
        mpls_label = '500'
        segment_list = 'smoketest-mpls-only-segment-list'
        index_value = '0'

        self.cli_set(base_path + ['segment-list', segment_list, 'index', 'value', index_value, 'mpls', 'label', mpls_label])
        self.cli_commit()

        frrconfig = self.getFRRconfig(f'segment-routing', daemon='pathd')
        self.assertIn(f'segment-routing', frrconfig)
        self.assertIn(f' traffic-eng', frrconfig)
        self.assertIn(f'  mpls-te on', frrconfig)
        self.assertIn(f'  segment-list {segment_list}', frrconfig)
        self.assertIn(f'   index {index_value} mpls label {mpls_label}', frrconfig)

        self.cli_delete(base_path)
        self.cli_commit()

    def test_segment_routing_05_mpls_label_and_adjacency(self):
        # Add segment-list with an mpls value and adjacency
        base_path = ['protocols', 'segment-routing', 'traffic-engineering']
        mpls_label = '1000'
        segment_list = 'smoketest-mpls-with-adjacency-segment-list'
        index_value = '0'

        addresses = {'ipv4' : {'source_identifier' : '192.168.255.1', 'destination_identifier' : '192.168.255.2'}, 
                     'ipv6' : {'source_identifier' : '2003::1', 'destination_identifier' : '2003::2'}}

        for address_family in ['ipv4', 'ipv6']:
            source_identifier = addresses[address_family]['source_identifier']
            destination_identifier = addresses[address_family]['destination_identifier']
            self.cli_set(base_path + ['segment-list', segment_list, 'index', 'value', index_value, 'mpls', 'label', mpls_label])
            self.cli_set(base_path + ['segment-list', segment_list, 'index', 'value', index_value, 'nai', 'adjacency', address_family, 'source-identifier', source_identifier])
            self.cli_set(base_path + ['segment-list', segment_list, 'index', 'value', index_value, 'nai', 'adjacency', address_family, 'destination-identifier', destination_identifier])
            self.cli_commit()

            frrconfig = self.getFRRconfig(f'segment-routing', daemon='pathd')
            self.assertIn(f'segment-routing', frrconfig)
            self.assertIn(f' traffic-eng', frrconfig)
            self.assertIn(f'  mpls-te on', frrconfig)
            self.assertIn(f'  segment-list {segment_list}', frrconfig)
            self.assertIn(f'   index {index_value} mpls label {mpls_label} nai adjacency {source_identifier} {destination_identifier}', frrconfig)

            self.cli_delete(base_path)
            self.cli_commit()


    def test_segment_routing_06_mpls_label_and_prefix(self):
        # Add segment-list with an mpls value and prefix
        base_path = ['protocols', 'segment-routing', 'traffic-engineering']
        mpls_label = '1500'
        segment_list = 'smoketest-mpls-with-prefix-segment-list'
        index_value = '0'

        prefixes = {'ipv4' : {'prefix' : '192.168.255.0/24'}, 
                    'ipv6' : {'prefix' : '2003::/120'}}

        for address_family in ['ipv4', 'ipv6']:
            for algorithm_type in ['spf', 'strict-spf']:
                prefix = prefixes[address_family]['prefix']
                self.cli_set(base_path + ['segment-list', segment_list, 'index', 'value', index_value, 'mpls', 'label', mpls_label])
                self.cli_set(base_path + ['segment-list', segment_list, 'index', 'value', index_value, 'nai', 'prefix', address_family, 'prefix-identifier', prefix, 'algorithm', algorithm_type])
                self.cli_commit()

                frrconfig = self.getFRRconfig(f'segment-routing', daemon='pathd')
                self.assertIn(f'segment-routing', frrconfig)
                self.assertIn(f' traffic-eng', frrconfig)
                self.assertIn(f'  mpls-te on', frrconfig)
                self.assertIn(f'  segment-list {segment_list}', frrconfig)
                if algorithm_type == 'spf':
                    self.assertIn(f'   index {index_value} mpls label {mpls_label} nai prefix {prefix} algorithm 0', frrconfig)
                elif algorithm_type == 'strict-spf':
                    self.assertIn(f'   index {index_value} mpls label {mpls_label} nai prefix {prefix} algorithm 1', frrconfig)

                self.cli_delete(base_path)
                self.cli_commit()


if __name__ == '__main__':
    unittest.main(verbosity=2)
