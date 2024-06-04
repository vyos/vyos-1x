#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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

PROCESS_NAME = 'isisd'
base_path = ['protocols', 'isis']

domain = 'VyOS'
net = '49.0001.1921.6800.1002.00'

class TestProtocolsISIS(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._interfaces = Section.interfaces('ethernet')
        # call base-classes classmethod
        super(TestProtocolsISIS, cls).setUpClass()
        # Retrieve FRR daemon PID - it is not allowed to crash, thus PID must remain the same
        cls.daemon_pid = process_named_running(PROCESS_NAME)
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)
        cls.cli_delete(cls, ['vrf'])

    def tearDown(self):
        # cleanup any possible VRF mess
        self.cli_delete(['vrf'])
        # always destrox the entire isisd configuration to make the processes
        # life as hard as possible
        self.cli_delete(base_path)
        self.cli_commit()

        # check process health and continuity
        self.assertEqual(self.daemon_pid, process_named_running(PROCESS_NAME))

    def isis_base_config(self):
        self.cli_set(base_path + ['net', net])
        for interface in self._interfaces:
            self.cli_set(base_path + ['interface', interface])

    def test_isis_01_redistribute(self):
        prefix_list = 'EXPORT-ISIS'
        route_map = 'EXPORT-ISIS'
        rule = '10'
        metric_style = 'transition'

        self.cli_set(['policy', 'prefix-list', prefix_list, 'rule', rule, 'action', 'permit'])
        self.cli_set(['policy', 'prefix-list', prefix_list, 'rule', rule, 'prefix', '203.0.113.0/24'])
        self.cli_set(['policy', 'route-map', route_map, 'rule', rule, 'action', 'permit'])
        self.cli_set(['policy', 'route-map', route_map, 'rule', rule, 'match', 'ip', 'address', 'prefix-list', prefix_list])

        self.cli_set(base_path)

        # verify() - net id and interface are mandatory
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.isis_base_config()

        self.cli_set(base_path + ['redistribute', 'ipv4', 'connected'])
        # verify() - Redistribute level-1 or level-2 should be specified
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['redistribute', 'ipv4', 'connected', 'level-2', 'route-map', route_map])
        self.cli_set(base_path + ['metric-style', metric_style])
        self.cli_set(base_path + ['log-adjacency-changes'])

        # Commit all changes
        self.cli_commit()

        # Verify all changes
        tmp = self.getFRRconfig(f'router isis {domain}', daemon='isisd')
        self.assertIn(f' net {net}', tmp)
        self.assertIn(f' metric-style {metric_style}', tmp)
        self.assertIn(f' log-adjacency-changes', tmp)
        self.assertIn(f' redistribute ipv4 connected level-2 route-map {route_map}', tmp)

        for interface in self._interfaces:
            tmp = self.getFRRconfig(f'interface {interface}', daemon='isisd')
            self.assertIn(f' ip router isis {domain}', tmp)
            self.assertIn(f' ipv6 router isis {domain}', tmp)

        self.cli_delete(['policy', 'route-map', route_map])
        self.cli_delete(['policy', 'prefix-list', prefix_list])

    def test_isis_02_vrfs(self):
        vrfs = ['red', 'green', 'blue']
        # It is safe to assume that when the basic VRF test works, all other
        # IS-IS related features work, as we entirely inherit the CLI templates
        # and Jinja2 FRR template.
        table = '1000'
        vrf = 'red'
        vrf_base = ['vrf', 'name', vrf]
        vrf_iface = 'eth1'
        self.cli_set(vrf_base + ['table', table])
        self.cli_set(vrf_base + ['protocols', 'isis', 'net', net])
        self.cli_set(vrf_base + ['protocols', 'isis', 'interface', vrf_iface])
        self.cli_set(vrf_base + ['protocols', 'isis', 'advertise-high-metrics'])
        self.cli_set(vrf_base + ['protocols', 'isis', 'advertise-passive-only'])
        self.cli_set(['interfaces', 'ethernet', vrf_iface, 'vrf', vrf])

        # Also set a default VRF IS-IS config
        self.cli_set(base_path + ['net', net])
        self.cli_set(base_path + ['interface', 'eth0'])
        self.cli_commit()

        # Verify FRR isisd configuration
        tmp = self.getFRRconfig(f'router isis {domain}', daemon='isisd')
        self.assertIn(f'router isis {domain}', tmp)
        self.assertIn(f' net {net}', tmp)

        tmp = self.getFRRconfig(f'router isis {domain} vrf {vrf}', daemon='isisd')
        self.assertIn(f'router isis {domain} vrf {vrf}', tmp)
        self.assertIn(f' net {net}', tmp)
        self.assertIn(f' advertise-high-metrics', tmp)
        self.assertIn(f' advertise-passive-only', tmp)

        self.cli_delete(['vrf', 'name', vrf])
        self.cli_delete(['interfaces', 'ethernet', vrf_iface, 'vrf'])

    def test_isis_04_default_information(self):
        metric = '50'
        route_map = 'default-foo-'

        self.isis_base_config()
        for afi in ['ipv4', 'ipv6']:
            for level in ['level-1', 'level-2']:
                self.cli_set(base_path + ['default-information', 'originate', afi, level, 'always'])
                self.cli_set(base_path + ['default-information', 'originate', afi, level, 'metric', metric])
                self.cli_set(base_path + ['default-information', 'originate', afi, level, 'route-map', route_map + level + afi])

        # Commit all changes
        self.cli_commit()

        # Verify all changes
        tmp = self.getFRRconfig(f'router isis {domain}', daemon='isisd')
        self.assertIn(f' net {net}', tmp)

        for afi in ['ipv4', 'ipv6']:
            for level in ['level-1', 'level-2']:
                route_map_name = route_map + level + afi
                self.assertIn(f' default-information originate {afi} {level} always route-map {route_map_name} metric {metric}', tmp)


    def test_isis_05_password(self):
        password = 'foo'

        self.isis_base_config()
        for interface in self._interfaces:
            self.cli_set(base_path + ['interface', interface, 'password', 'plaintext-password', f'{password}-{interface}'])

        self.cli_set(base_path + ['area-password', 'plaintext-password', password])
        self.cli_set(base_path + ['area-password', 'md5', password])
        self.cli_set(base_path + ['domain-password', 'plaintext-password', password])
        self.cli_set(base_path + ['domain-password', 'md5', password])

        # verify() - can not use both md5 and plaintext-password for area-password
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['area-password', 'md5', password])

        # verify() - can not use both md5 and plaintext-password for domain-password
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['domain-password', 'md5', password])

        # Commit all changes
        self.cli_commit()

        # Verify all changes
        tmp = self.getFRRconfig(f'router isis {domain}', daemon='isisd')
        self.assertIn(f' net {net}', tmp)
        self.assertIn(f' domain-password clear {password}', tmp)
        self.assertIn(f' area-password clear {password}', tmp)

        for interface in self._interfaces:
            tmp = self.getFRRconfig(f'interface {interface}', daemon='isisd')
            self.assertIn(f' isis password clear {password}-{interface}', tmp)

    def test_isis_06_spf_delay_bfd(self):
        network = 'point-to-point'
        holddown = '10'
        init_delay = '50'
        long_delay = '200'
        short_delay = '100'
        time_to_learn = '75'
        bfd_profile = 'isis-bfd'

        self.cli_set(base_path + ['net', net])
        for interface in self._interfaces:
            self.cli_set(base_path + ['interface', interface, 'network', network])
            self.cli_set(base_path + ['interface', interface, 'bfd', 'profile', bfd_profile])

        self.cli_set(base_path + ['spf-delay-ietf', 'holddown', holddown])
        # verify() - All types of spf-delay must be configured
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['spf-delay-ietf', 'init-delay', init_delay])
        # verify() - All types of spf-delay must be configured
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['spf-delay-ietf', 'long-delay', long_delay])
        # verify() - All types of spf-delay must be configured
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['spf-delay-ietf', 'short-delay', short_delay])
        # verify() - All types of spf-delay must be configured
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['spf-delay-ietf', 'time-to-learn', time_to_learn])

        # Commit all changes
        self.cli_commit()

        # Verify all changes
        tmp = self.getFRRconfig(f'router isis {domain}', daemon='isisd')
        self.assertIn(f' net {net}', tmp)
        self.assertIn(f' spf-delay-ietf init-delay {init_delay} short-delay {short_delay} long-delay {long_delay} holddown {holddown} time-to-learn {time_to_learn}', tmp)

        for interface in self._interfaces:
            tmp = self.getFRRconfig(f'interface {interface}', daemon='isisd')
            self.assertIn(f' ip router isis {domain}', tmp)
            self.assertIn(f' ipv6 router isis {domain}', tmp)
            self.assertIn(f' isis network {network}', tmp)
            self.assertIn(f' isis bfd', tmp)
            self.assertIn(f' isis bfd profile {bfd_profile}', tmp)

    def test_isis_07_segment_routing_configuration(self):
        global_block_low = "300"
        global_block_high = "399"
        local_block_low = "400"
        local_block_high = "499"
        interface = 'lo'
        maximum_stack_size = '5'
        prefix_one = '192.168.0.1/32'
        prefix_two = '192.168.0.2/32'
        prefix_three = '192.168.0.3/32'
        prefix_four = '192.168.0.4/32'
        prefix_one_value = '1'
        prefix_two_value = '2'
        prefix_three_value = '60000'
        prefix_four_value = '65000'

        self.cli_set(base_path + ['net', net])
        self.cli_set(base_path + ['interface', interface])
        self.cli_set(base_path + ['segment-routing', 'maximum-label-depth', maximum_stack_size])
        self.cli_set(base_path + ['segment-routing', 'global-block', 'low-label-value', global_block_low])
        self.cli_set(base_path + ['segment-routing', 'global-block', 'high-label-value', global_block_high])
        self.cli_set(base_path + ['segment-routing', 'local-block', 'low-label-value', local_block_low])
        self.cli_set(base_path + ['segment-routing', 'local-block', 'high-label-value', local_block_high])
        self.cli_set(base_path + ['segment-routing', 'prefix', prefix_one, 'index', 'value', prefix_one_value])
        self.cli_set(base_path + ['segment-routing', 'prefix', prefix_one, 'index', 'explicit-null'])
        self.cli_set(base_path + ['segment-routing', 'prefix', prefix_two, 'index', 'value', prefix_two_value])
        self.cli_set(base_path + ['segment-routing', 'prefix', prefix_two, 'index', 'no-php-flag'])
        self.cli_set(base_path + ['segment-routing', 'prefix', prefix_three, 'absolute', 'value',  prefix_three_value])
        self.cli_set(base_path + ['segment-routing', 'prefix', prefix_three, 'absolute', 'explicit-null'])
        self.cli_set(base_path + ['segment-routing', 'prefix', prefix_four, 'absolute', 'value', prefix_four_value])
        self.cli_set(base_path + ['segment-routing', 'prefix', prefix_four, 'absolute', 'no-php-flag'])

        # Commit all changes
        self.cli_commit()

        # Verify all changes
        tmp = self.getFRRconfig(f'router isis {domain}', daemon='isisd')
        self.assertIn(f' net {net}', tmp)
        self.assertIn(f' segment-routing on', tmp)
        self.assertIn(f' segment-routing global-block {global_block_low} {global_block_high} local-block {local_block_low} {local_block_high}', tmp)
        self.assertIn(f' segment-routing node-msd {maximum_stack_size}', tmp)
        self.assertIn(f' segment-routing prefix {prefix_one} index {prefix_one_value} explicit-null', tmp)
        self.assertIn(f' segment-routing prefix {prefix_two} index {prefix_two_value} no-php-flag', tmp)
        self.assertIn(f' segment-routing prefix {prefix_three} absolute {prefix_three_value} explicit-null', tmp)
        self.assertIn(f' segment-routing prefix {prefix_four} absolute {prefix_four_value} no-php-flag', tmp)

    def test_isis_08_ldp_sync(self):
        holddown = "500"
        interface = 'lo'

        self.cli_set(base_path + ['net', net])
        self.cli_set(base_path + ['interface', interface])
        self.cli_set(base_path + ['ldp-sync', 'holddown', holddown])

        # Commit main ISIS changes
        self.cli_commit()

        # Verify main ISIS changes
        tmp = self.getFRRconfig(f'router isis {domain}', daemon='isisd')
        self.assertIn(f' net {net}', tmp)
        self.assertIn(f' mpls ldp-sync', tmp)
        self.assertIn(f' mpls ldp-sync holddown {holddown}', tmp)

        for interface in self._interfaces:
            self.cli_set(base_path + ['interface', interface, 'ldp-sync', 'holddown', holddown])

        # Commit interface changes for holddown
        self.cli_commit()

        for interface in self._interfaces:
            # Verify interface changes for holddown
            tmp = self.getFRRconfig(f'interface {interface}', daemon='isisd')
            self.assertIn(f'interface {interface}', tmp)
            self.assertIn(f' ip router isis {domain}', tmp)
            self.assertIn(f' ipv6 router isis {domain}', tmp)
            self.assertIn(f' isis mpls ldp-sync holddown {holddown}', tmp)

        for interface in self._interfaces:
            self.cli_set(base_path + ['interface', interface, 'ldp-sync', 'disable'])

        # Commit interface changes for disable
        self.cli_commit()

        for interface in self._interfaces:
            # Verify interface changes for disable
            tmp = self.getFRRconfig(f'interface {interface}', daemon='isisd')
            self.assertIn(f'interface {interface}', tmp)
            self.assertIn(f' ip router isis {domain}', tmp)
            self.assertIn(f' ipv6 router isis {domain}', tmp)
            self.assertIn(f' no isis mpls ldp-sync', tmp)

    def test_isis_09_lfa(self):
        prefix_list = 'lfa-prefix-list-test-1'
        prefix_list_address = '192.168.255.255/32'
        interface = 'lo'

        self.cli_set(base_path + ['net', net])
        self.cli_set(base_path + ['interface', interface])
        self.cli_set(['policy', 'prefix-list', prefix_list, 'rule', '1', 'action', 'permit'])
        self.cli_set(['policy', 'prefix-list', prefix_list, 'rule', '1', 'prefix', prefix_list_address])

        # Commit main ISIS changes
        self.cli_commit()

        # Add remote portion of LFA with prefix list with validation
        for level in ['level-1', 'level-2']:
            self.cli_set(base_path + ['fast-reroute', 'lfa', 'remote', 'prefix-list', prefix_list, level])
            self.cli_commit()
            tmp = self.getFRRconfig(f'router isis {domain}', daemon='isisd')
            self.assertIn(f' net {net}', tmp)
            self.assertIn(f' fast-reroute remote-lfa prefix-list {prefix_list} {level}', tmp)
            self.cli_delete(base_path + ['fast-reroute'])
            self.cli_commit()

        # Add local portion of LFA load-sharing portion with validation
        for level in ['level-1', 'level-2']:
            self.cli_set(base_path + ['fast-reroute', 'lfa', 'local', 'load-sharing', 'disable', level])
            self.cli_commit()
            tmp = self.getFRRconfig(f'router isis {domain}', daemon='isisd')
            self.assertIn(f' net {net}', tmp)
            self.assertIn(f' fast-reroute load-sharing disable {level}', tmp)
            self.cli_delete(base_path + ['fast-reroute'])
            self.cli_commit()

        # Add local portion of LFA priority-limit portion with validation
        for priority in ['critical', 'high', 'medium']:
            for level in ['level-1', 'level-2']:
                self.cli_set(base_path + ['fast-reroute', 'lfa', 'local', 'priority-limit', priority, level])
                self.cli_commit()
                tmp = self.getFRRconfig(f'router isis {domain}', daemon='isisd')
                self.assertIn(f' net {net}', tmp)
                self.assertIn(f' fast-reroute priority-limit {priority} {level}', tmp)
                self.cli_delete(base_path + ['fast-reroute'])
                self.cli_commit()

        # Add local portion of LFA tiebreaker portion with validation
        index = '100'
        for tiebreaker in ['downstream','lowest-backup-metric','node-protecting']:
            for level in ['level-1', 'level-2']:
                self.cli_set(base_path + ['fast-reroute', 'lfa', 'local', 'tiebreaker', tiebreaker, 'index', index, level])
                self.cli_commit()
                tmp = self.getFRRconfig(f'router isis {domain}', daemon='isisd')
                self.assertIn(f' net {net}', tmp)
                self.assertIn(f' fast-reroute lfa tiebreaker {tiebreaker} index {index} {level}', tmp)
                self.cli_delete(base_path + ['fast-reroute'])
                self.cli_commit()

        # Clean up and remove prefix list
        self.cli_delete(['policy', 'prefix-list', prefix_list])
        self.cli_commit()

    def test_isis_10_topology(self):
        topologies = ['ipv4-multicast', 'ipv4-mgmt', 'ipv6-unicast', 'ipv6-multicast', 'ipv6-mgmt']
        interface = 'lo'

        # Set a basic IS-IS config
        self.cli_set(base_path + ['net', net])
        self.cli_set(base_path + ['interface', interface])
        for topology in topologies:
            self.cli_set(base_path + ['topology', topology])
            self.cli_commit()
            tmp = self.getFRRconfig(f'router isis {domain}', daemon='isisd')
            self.assertIn(f' net {net}', tmp)
            self.assertIn(f' topology {topology}', tmp)

if __name__ == '__main__':
    unittest.main(verbosity=2)
