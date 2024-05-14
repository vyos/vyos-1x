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

from time import sleep
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Section
from vyos.utils.process import process_named_running

PROCESS_NAME = 'ospfd'
base_path = ['protocols', 'ospf']

route_map = 'foo-bar-baz10'

class TestProtocolsOSPF(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProtocolsOSPF, cls).setUpClass()

        # Retrieve FRR daemon PID - it is not allowed to crash, thus PID must remain the same
        cls.daemon_pid = process_named_running(PROCESS_NAME)

        cls.cli_set(cls, ['policy', 'route-map', route_map, 'rule', '10', 'action', 'permit'])
        cls.cli_set(cls, ['policy', 'route-map', route_map, 'rule', '20', 'action', 'permit'])

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['policy', 'route-map', route_map])
        super(TestProtocolsOSPF, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        # check process health and continuity
        self.assertEqual(self.daemon_pid, process_named_running(PROCESS_NAME))

    def test_ospf_01_defaults(self):
        # commit changes
        self.cli_set(base_path)
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' auto-cost reference-bandwidth 100', frrconfig)
        self.assertIn(f' timers throttle spf 200 1000 10000', frrconfig) # defaults

    def test_ospf_02_simple(self):
        router_id = '127.0.0.1'
        abr_type = 'ibm'
        bandwidth = '1000'
        metric = '123'

        self.cli_set(base_path + ['auto-cost', 'reference-bandwidth', bandwidth])
        self.cli_set(base_path + ['parameters', 'router-id', router_id])
        self.cli_set(base_path + ['parameters', 'abr-type', abr_type])
        self.cli_set(base_path + ['parameters', 'opaque-lsa'])
        self.cli_set(base_path + ['parameters', 'rfc1583-compatibility'])
        self.cli_set(base_path + ['log-adjacency-changes', 'detail'])
        self.cli_set(base_path + ['default-metric', metric])
        self.cli_set(base_path + ['passive-interface', 'default'])
        self.cli_set(base_path + ['area', '10', 'area-type', 'stub'])
        self.cli_set(base_path + ['area', '10', 'network', '10.0.0.0/16'])
        self.cli_set(base_path + ['area', '10', 'range', '10.0.1.0/24'])
        self.cli_set(base_path + ['area', '10', 'range', '10.0.2.0/24', 'not-advertise'])

        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' compatible rfc1583', frrconfig)
        self.assertIn(f' auto-cost reference-bandwidth {bandwidth}', frrconfig)
        self.assertIn(f' ospf router-id {router_id}', frrconfig)
        self.assertIn(f' ospf abr-type {abr_type}', frrconfig)
        self.assertIn(f' timers throttle spf 200 1000 10000', frrconfig) # defaults
        self.assertIn(f' capability opaque', frrconfig)
        self.assertIn(f' default-metric {metric}', frrconfig)
        self.assertIn(f' passive-interface default', frrconfig)
        self.assertIn(f' area 10 stub', frrconfig)
        self.assertIn(f' network 10.0.0.0/16 area 10', frrconfig)
        self.assertIn(f' area 10 range 10.0.1.0/24', frrconfig)
        self.assertNotIn(f' area 10 range 10.0.1.0/24 not-advertise', frrconfig)
        self.assertIn(f' area 10 range 10.0.2.0/24 not-advertise', frrconfig)


    def test_ospf_03_access_list(self):
        acl = '100'
        seq = '10'
        protocols = ['bgp', 'connected', 'isis', 'kernel', 'rip', 'static']

        self.cli_set(['policy', 'access-list', acl, 'rule', seq, 'action', 'permit'])
        self.cli_set(['policy', 'access-list', acl, 'rule', seq, 'source', 'any'])
        self.cli_set(['policy', 'access-list', acl, 'rule', seq, 'destination', 'any'])
        for ptotocol in protocols:
            self.cli_set(base_path + ['access-list', acl, 'export', ptotocol])

        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' timers throttle spf 200 1000 10000', frrconfig) # defaults
        for ptotocol in protocols:
            self.assertIn(f' distribute-list {acl} out {ptotocol}', frrconfig) # defaults
        self.cli_delete(['policy', 'access-list', acl])


    def test_ospf_04_default_originate(self):
        seq = '100'
        metric = '50'
        metric_type = '1'

        self.cli_set(base_path + ['default-information', 'originate', 'metric', metric])
        self.cli_set(base_path + ['default-information', 'originate', 'metric-type', metric_type])
        self.cli_set(base_path + ['default-information', 'originate', 'route-map', route_map])

        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' timers throttle spf 200 1000 10000', frrconfig) # defaults
        self.assertIn(f' default-information originate metric {metric} metric-type {metric_type} route-map {route_map}', frrconfig)

        # Now set 'always'
        self.cli_set(base_path + ['default-information', 'originate', 'always'])
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f' default-information originate always metric {metric} metric-type {metric_type} route-map {route_map}', frrconfig)


    def test_ospf_05_options(self):
        global_distance = '128'
        intra_area = '100'
        inter_area = '110'
        external = '120'
        on_startup = '30'
        on_shutdown = '60'
        refresh = '50'
        aggregation_timer = '100'
        summary_nets = {
            '10.0.1.0/24' : {},
            '10.0.2.0/24' : {'tag' : '50'},
            '10.0.3.0/24' : {'no_advertise' : {}},
         }

        self.cli_set(base_path + ['distance', 'global', global_distance])
        self.cli_set(base_path + ['distance', 'ospf', 'external', external])
        self.cli_set(base_path + ['distance', 'ospf', 'intra-area', intra_area])

        self.cli_set(base_path + ['max-metric', 'router-lsa', 'on-startup', on_startup])
        self.cli_set(base_path + ['max-metric', 'router-lsa', 'on-shutdown', on_shutdown])

        self.cli_set(base_path + ['mpls-te', 'enable'])
        self.cli_set(base_path + ['refresh', 'timers', refresh])

        self.cli_set(base_path + ['aggregation', 'timer', aggregation_timer])

        for summary, summary_options in summary_nets.items():
            self.cli_set(base_path + ['summary-address', summary])
            if 'tag' in summary_options:
                self.cli_set(base_path + ['summary-address', summary, 'tag', summary_options['tag']])
            if 'no_advertise' in summary_options:
                self.cli_set(base_path + ['summary-address', summary, 'no-advertise'])

        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' mpls-te on', frrconfig)
        self.assertIn(f' mpls-te router-address 0.0.0.0', frrconfig) # default
        self.assertIn(f' distance {global_distance}', frrconfig)
        self.assertIn(f' distance ospf intra-area {intra_area} external {external}', frrconfig)
        self.assertIn(f' max-metric router-lsa on-startup {on_startup}', frrconfig)
        self.assertIn(f' max-metric router-lsa on-shutdown {on_shutdown}', frrconfig)
        self.assertIn(f' refresh timer {refresh}', frrconfig)

        self.assertIn(f' aggregation timer {aggregation_timer}', frrconfig)
        for summary, summary_options in summary_nets.items():
            self.assertIn(f' summary-address {summary}', frrconfig)
            if 'tag' in summary_options:
                tag = summary_options['tag']
                self.assertIn(f' summary-address {summary} tag {tag}', frrconfig)
            if 'no_advertise' in summary_options:
                self.assertIn(f' summary-address {summary} no-advertise', frrconfig)

        # enable inter-area
        self.cli_set(base_path + ['distance', 'ospf', 'inter-area', inter_area])
        self.cli_commit()

        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f' distance ospf intra-area {intra_area} inter-area {inter_area} external {external}', frrconfig)


    def test_ospf_06_neighbor(self):
        priority = '10'
        poll_interval = '20'
        neighbors = ['1.1.1.1', '2.2.2.2', '3.3.3.3']
        for neighbor in neighbors:
            self.cli_set(base_path + ['neighbor', neighbor, 'priority', priority])
            self.cli_set(base_path + ['neighbor', neighbor, 'poll-interval', poll_interval])

        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f'router ospf', frrconfig)
        for neighbor in neighbors:
            self.assertIn(f' neighbor {neighbor} priority {priority} poll-interval {poll_interval}', frrconfig) # default

    def test_ospf_07_redistribute(self):
        metric = '15'
        metric_type = '1'
        redistribute = ['babel', 'bgp', 'connected', 'isis', 'kernel', 'rip', 'static']

        for protocol in redistribute:
            self.cli_set(base_path + ['redistribute', protocol, 'metric', metric])
            self.cli_set(base_path + ['redistribute', protocol, 'route-map', route_map])
            self.cli_set(base_path + ['redistribute', protocol, 'metric-type', metric_type])

        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f'router ospf', frrconfig)
        for protocol in redistribute:
            self.assertIn(f' redistribute {protocol} metric {metric} metric-type {metric_type} route-map {route_map}', frrconfig)

    def test_ospf_08_virtual_link(self):
        networks = ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']
        area = '10'
        shortcut = 'enable'
        virtual_link = '192.0.2.1'
        hello = '6'
        retransmit = '5'
        transmit = '5'
        dead = '40'

        self.cli_set(base_path + ['area', area, 'shortcut', shortcut])
        self.cli_set(base_path + ['area', area, 'virtual-link', virtual_link, 'hello-interval', hello])
        self.cli_set(base_path + ['area', area, 'virtual-link', virtual_link, 'retransmit-interval', retransmit])
        self.cli_set(base_path + ['area', area, 'virtual-link', virtual_link, 'transmit-delay', transmit])
        self.cli_set(base_path + ['area', area, 'virtual-link', virtual_link, 'dead-interval', dead])
        for network in networks:
            self.cli_set(base_path + ['area', area, 'network', network])

        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' area {area} shortcut {shortcut}', frrconfig)
        self.assertIn(f' area {area} virtual-link {virtual_link} hello-interval {hello} retransmit-interval {retransmit} transmit-delay {transmit} dead-interval {dead}', frrconfig)
        for network in networks:
            self.assertIn(f' network {network} area {area}', frrconfig)


    def test_ospf_09_interface_configuration(self):
        interfaces = Section.interfaces('ethernet')
        password = 'vyos1234'
        bandwidth = '10000'
        cost = '150'
        network = 'point-to-point'
        priority = '200'
        bfd_profile = 'vyos-test'

        self.cli_set(base_path + ['passive-interface', 'default'])
        for interface in interfaces:
            base_interface = base_path + ['interface', interface]
            self.cli_set(base_interface + ['authentication', 'plaintext-password', password])
            self.cli_set(base_interface + ['bandwidth', bandwidth])
            self.cli_set(base_interface + ['bfd', 'profile', bfd_profile])
            self.cli_set(base_interface + ['cost', cost])
            self.cli_set(base_interface + ['mtu-ignore'])
            self.cli_set(base_interface + ['network', network])
            self.cli_set(base_interface + ['priority', priority])
            self.cli_set(base_interface + ['passive', 'disable'])

        # commit changes
        self.cli_commit()

        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' passive-interface default', frrconfig)

        for interface in interfaces:
            # Can not use daemon for getFRRconfig() as bandwidth parameter belongs to zebra process
            config = self.getFRRconfig(f'interface {interface}')
            self.assertIn(f'interface {interface}', config)
            self.assertIn(f' ip ospf authentication-key {password}', config)
            self.assertIn(f' ip ospf bfd', config)
            self.assertIn(f' ip ospf bfd profile {bfd_profile}', config)
            self.assertIn(f' ip ospf cost {cost}', config)
            self.assertIn(f' ip ospf mtu-ignore', config)
            self.assertIn(f' ip ospf network {network}', config)
            self.assertIn(f' ip ospf priority {priority}', config)
            self.assertIn(f' no ip ospf passive', config)
            self.assertIn(f' bandwidth {bandwidth}', config)

        # T5467: Remove interface from OSPF process and VRF
        self.cli_delete(base_path + ['interface'])
        self.cli_commit()

        for interface in interfaces:
            # T5467: It must also be removed from FRR config
            frrconfig = self.getFRRconfig(f'interface {interface}', daemon=PROCESS_NAME)
            self.assertNotIn(f'interface {interface}', frrconfig)
            # There should be no OSPF related command at all under the interface
            self.assertNotIn(f' ip ospf', frrconfig)

    def test_ospf_11_interface_area(self):
        area = '0'
        interfaces = Section.interfaces('ethernet')

        self.cli_set(base_path + ['area', area, 'network', '10.0.0.0/8'])
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface, 'area', area])

        # we can not have bot area network and interface area set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['area', area, 'network'])

        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f'router ospf', frrconfig)

        for interface in interfaces:
            config = self.getFRRconfig(f'interface {interface}', daemon=PROCESS_NAME)
            self.assertIn(f'interface {interface}', config)
            self.assertIn(f' ip ospf area {area}', config)

    def test_ospf_12_vrfs(self):
        # It is safe to assume that when the basic VRF test works, all
        # other OSPF related features work, as we entirely inherit the CLI
        # templates and Jinja2 FRR template.
        table = '1000'
        vrf = 'blue'
        vrf_base = ['vrf', 'name', vrf]
        vrf_iface = 'eth1'
        area = '1'

        self.cli_set(vrf_base + ['table', table])
        self.cli_set(vrf_base + ['protocols', 'ospf', 'interface', vrf_iface, 'area', area])
        self.cli_set(['interfaces', 'ethernet', vrf_iface, 'vrf', vrf])

        # Also set a default VRF OSPF config
        self.cli_set(base_path)
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' auto-cost reference-bandwidth 100', frrconfig)
        self.assertIn(f' timers throttle spf 200 1000 10000', frrconfig) # defaults

        frrconfig = self.getFRRconfig(f'router ospf vrf {vrf}', daemon=PROCESS_NAME)
        self.assertIn(f'router ospf vrf {vrf}', frrconfig)
        self.assertIn(f' auto-cost reference-bandwidth 100', frrconfig)
        self.assertIn(f' timers throttle spf 200 1000 10000', frrconfig) # defaults

        frrconfig = self.getFRRconfig(f'interface {vrf_iface}', daemon=PROCESS_NAME)
        self.assertIn(f'interface {vrf_iface}', frrconfig)
        self.assertIn(f' ip ospf area {area}', frrconfig)

        # T5467: Remove interface from OSPF process and VRF
        self.cli_delete(vrf_base + ['protocols', 'ospf', 'interface'])
        self.cli_delete(['interfaces', 'ethernet', vrf_iface, 'vrf'])
        self.cli_commit()

        # T5467: It must also be removed from FRR config
        frrconfig = self.getFRRconfig(f'interface {vrf_iface}', daemon=PROCESS_NAME)
        self.assertNotIn(f'interface {vrf_iface}', frrconfig)
        # There should be no OSPF related command at all under the interface
        self.assertNotIn(f' ip ospf', frrconfig)

        # cleanup
        self.cli_delete(['vrf', 'name', vrf])
        self.cli_delete(['interfaces', 'ethernet', vrf_iface, 'vrf'])

    def test_ospf_13_export_list(self):
        # Verify explort-list works on ospf-area
        acl = '100'
        seq = '10'
        area = '0.0.0.10'
        network = '10.0.0.0/8'

        self.cli_set(['policy', 'access-list', acl, 'rule', seq, 'action', 'permit'])
        self.cli_set(['policy', 'access-list', acl, 'rule', seq, 'source', 'any'])
        self.cli_set(['policy', 'access-list', acl, 'rule', seq, 'destination', 'any'])
        self.cli_set(base_path + ['area', area, 'network', network])
        self.cli_set(base_path + ['area', area, 'export-list', acl])

        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' timers throttle spf 200 1000 10000', frrconfig) # default
        self.assertIn(f' network {network} area {area}', frrconfig)
        self.assertIn(f' area {area} export-list {acl}', frrconfig)


    def test_ospf_14_segment_routing_configuration(self):
        global_block_low = "300"
        global_block_high = "399"
        local_block_low = "400"
        local_block_high = "499"
        interface = 'lo'
        maximum_stack_size = '5'
        prefix_one = '192.168.0.1/32'
        prefix_two = '192.168.0.2/32'
        prefix_one_value = '1'
        prefix_two_value = '2'

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

        # Commit all changes
        self.cli_commit()

        # Verify all changes
        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f' segment-routing on', frrconfig)
        self.assertIn(f' segment-routing global-block {global_block_low} {global_block_high} local-block {local_block_low} {local_block_high}', frrconfig)
        self.assertIn(f' segment-routing node-msd {maximum_stack_size}', frrconfig)
        self.assertIn(f' segment-routing prefix {prefix_one} index {prefix_one_value} explicit-null', frrconfig)
        self.assertIn(f' segment-routing prefix {prefix_two} index {prefix_two_value} no-php-flag', frrconfig)

    def test_ospf_15_ldp_sync(self):
        holddown = "500"
        interface = 'lo'
        interfaces = Section.interfaces('ethernet')

        self.cli_set(base_path + ['interface', interface])
        self.cli_set(base_path + ['ldp-sync', 'holddown', holddown])

        # Commit main OSPF changes
        self.cli_commit()

        sleep(10)

        # Verify main OSPF changes
        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' timers throttle spf 200 1000 10000', frrconfig)
        self.assertIn(f' mpls ldp-sync holddown {holddown}', frrconfig)

        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface, 'ldp-sync', 'holddown', holddown])

        # Commit interface changes for holddown
        self.cli_commit()

        for interface in interfaces:
            # Verify interface changes for holddown
            config = self.getFRRconfig(f'interface {interface}', daemon=PROCESS_NAME)
            self.assertIn(f'interface {interface}', config)
            self.assertIn(f' ip ospf dead-interval 40', config)
            self.assertIn(f' ip ospf mpls ldp-sync', config)
            self.assertIn(f' ip ospf mpls ldp-sync holddown {holddown}', config)

        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface, 'ldp-sync', 'disable'])

        # Commit interface changes for disable
        self.cli_commit()

        for interface in interfaces:
            # Verify interface changes for disable
            config = self.getFRRconfig(f'interface {interface}', daemon=PROCESS_NAME)
            self.assertIn(f'interface {interface}', config)
            self.assertIn(f' ip ospf dead-interval 40', config)
            self.assertIn(f' no ip ospf mpls ldp-sync', config)

    def test_ospf_16_graceful_restart(self):
        period = '300'
        supported_grace_time = '400'
        router_ids = ['192.0.2.1', '192.0.2.2']

        self.cli_set(base_path + ['capability', 'opaque'])
        self.cli_set(base_path + ['graceful-restart', 'grace-period', period])
        self.cli_set(base_path + ['graceful-restart', 'helper', 'planned-only'])
        self.cli_set(base_path + ['graceful-restart', 'helper', 'no-strict-lsa-checking'])
        self.cli_set(base_path + ['graceful-restart', 'helper', 'supported-grace-time', supported_grace_time])
        for router_id in router_ids:
            self.cli_set(base_path + ['graceful-restart', 'helper', 'enable', 'router-id', router_id])

        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' capability opaque', frrconfig)
        self.assertIn(f' graceful-restart grace-period {period}', frrconfig)
        self.assertIn(f' graceful-restart helper planned-only', frrconfig)
        self.assertIn(f' no graceful-restart helper strict-lsa-checking', frrconfig)
        self.assertIn(f' graceful-restart helper supported-grace-time {supported_grace_time}', frrconfig)
        for router_id in router_ids:
            self.assertIn(f' graceful-restart helper enable {router_id}', frrconfig)

    def test_ospf_17_duplicate_area_network(self):
        area0 = '0'
        area1 = '1'
        network = '10.0.0.0/8'

        self.cli_set(base_path + ['area', area0, 'network', network])

        # we can not have the same network defined on two areas
        self.cli_set(base_path + ['area', area1, 'network', network])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['area', area0])

        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf', daemon=PROCESS_NAME)
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' network {network} area {area1}', frrconfig)

if __name__ == '__main__':
    unittest.main(verbosity=2)
