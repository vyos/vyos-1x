#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

from vyos.configsession import ConfigSession
from vyos.ifconfig import Section
from vyos.util import cmd
from vyos.util import process_named_running

PROCESS_NAME = 'ospfd'
base_path = ['protocols', 'ospf']

route_map = 'foo-bar-baz10'

def getFRROSPFconfig():
    return cmd('vtysh -c "show run" | sed -n "/router ospf/,/^!/p"')

class TestProtocolsOSPF(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        self.session.set(['policy', 'route-map', route_map, 'rule', '10', 'action', 'permit'])
        self.session.set(['policy', 'route-map', route_map, 'rule', '20', 'action', 'permit'])

    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        self.session.delete(['policy', 'route-map', route_map])
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_ospf_01_defaults(self):
        # commit changes
        self.session.set(base_path)
        self.session.commit()

        # Verify FRR ospfd configuration
        frrconfig = getFRROSPFconfig()
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' auto-cost reference-bandwidth 100', frrconfig)
        self.assertIn(f' timers throttle spf 200 1000 10000', frrconfig) # defaults


    def test_ospf_02_simple(self):
        router_id = '127.0.0.1'
        abr_type = 'ibm'
        bandwidth = '1000'
        metric = '123'

        self.session.set(base_path + ['auto-cost', 'reference-bandwidth', bandwidth])
        self.session.set(base_path + ['parameters', 'router-id', router_id])
        self.session.set(base_path + ['parameters', 'abr-type', abr_type])
        self.session.set(base_path + ['log-adjacency-changes', 'detail'])
        self.session.set(base_path + ['default-metric', metric])

        # commit changes
        self.session.commit()

        # Verify FRR ospfd configuration
        frrconfig = getFRROSPFconfig()
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' auto-cost reference-bandwidth {bandwidth}', frrconfig)
        self.assertIn(f' ospf router-id {router_id}', frrconfig)
        self.assertIn(f' ospf abr-type {abr_type}', frrconfig)
        self.assertIn(f' timers throttle spf 200 1000 10000', frrconfig) # defaults
        self.assertIn(f' default-metric {metric}', frrconfig)


    def test_ospf_03_access_list(self):
        acl = '100'
        seq = '10'
        protocols = ['bgp', 'connected', 'kernel', 'rip', 'static']

        self.session.set(['policy', 'access-list', acl, 'rule', seq, 'action', 'permit'])
        self.session.set(['policy', 'access-list', acl, 'rule', seq, 'source', 'any'])
        self.session.set(['policy', 'access-list', acl, 'rule', seq, 'destination', 'any'])
        for ptotocol in protocols:
            self.session.set(base_path + ['access-list', acl, 'export', ptotocol])

        # commit changes
        self.session.commit()

        # Verify FRR ospfd configuration
        frrconfig = getFRROSPFconfig()
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' timers throttle spf 200 1000 10000', frrconfig) # defaults
        for ptotocol in protocols:
            self.assertIn(f' distribute-list {acl} out {ptotocol}', frrconfig) # defaults
        self.session.delete(['policy', 'access-list', acl])


    def test_ospf_04_default_originate(self):
        seq = '100'
        metric = '50'
        metric_type = '1'

        self.session.set(base_path + ['default-information', 'originate', 'metric', metric])
        self.session.set(base_path + ['default-information', 'originate', 'metric-type', metric_type])
        self.session.set(base_path + ['default-information', 'originate', 'route-map', route_map])

        # commit changes
        self.session.commit()

        # Verify FRR ospfd configuration
        frrconfig = getFRROSPFconfig()
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' timers throttle spf 200 1000 10000', frrconfig) # defaults
        self.assertIn(f' default-information originate metric {metric} metric-type {metric_type} route-map {route_map}', frrconfig)

        # Now set 'always'
        self.session.set(base_path + ['default-information', 'originate', 'always'])
        self.session.commit()

        # Verify FRR ospfd configuration
        frrconfig = getFRROSPFconfig()
        self.assertIn(f' default-information originate always metric {metric} metric-type {metric_type} route-map {route_map}', frrconfig)


    def test_ospf_05_options(self):
        global_distance = '128'
        intra_area = '100'
        inter_area = '110'
        external = '120'
        on_startup = '30'
        on_shutdown = '60'
        refresh = '50'

        self.session.set(base_path + ['distance', 'global', global_distance])
        self.session.set(base_path + ['distance', 'ospf', 'external', external])
        self.session.set(base_path + ['distance', 'ospf', 'intra-area', intra_area])

        self.session.set(base_path + ['max-metric', 'router-lsa', 'on-startup', on_startup])
        self.session.set(base_path + ['max-metric', 'router-lsa', 'on-shutdown', on_shutdown])

        self.session.set(base_path + ['mpls-te', 'enable'])
        self.session.set(base_path + ['refresh', 'timers', refresh])

        # commit changes
        self.session.commit()

        # Verify FRR ospfd configuration
        frrconfig = getFRROSPFconfig()
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' mpls-te on', frrconfig)
        self.assertIn(f' mpls-te router-address 0.0.0.0', frrconfig) # default
        self.assertIn(f' distance {global_distance}', frrconfig)
        self.assertIn(f' distance ospf intra-area {intra_area} external {external}', frrconfig)
        self.assertIn(f' max-metric router-lsa on-startup {on_startup}', frrconfig)
        self.assertIn(f' max-metric router-lsa on-shutdown {on_shutdown}', frrconfig)
        self.assertIn(f' refresh timer {refresh}', frrconfig)


        # enable inter-area
        self.session.set(base_path + ['distance', 'ospf', 'inter-area', inter_area])
        self.session.commit()

        frrconfig = getFRROSPFconfig()
        self.assertIn(f' distance ospf intra-area {intra_area} inter-area {inter_area} external {external}', frrconfig)


    def test_ospf_06_neighbor(self):
        priority = '10'
        poll_interval = '20'
        neighbors = ['1.1.1.1', '2.2.2.2', '3.3.3.3']
        for neighbor in neighbors:
            self.session.set(base_path + ['neighbor', neighbor, 'priority', priority])
            self.session.set(base_path + ['neighbor', neighbor, 'poll-interval', poll_interval])

        # commit changes
        self.session.commit()

        # Verify FRR ospfd configuration
        frrconfig = getFRROSPFconfig()
        self.assertIn(f'router ospf', frrconfig)
        for neighbor in neighbors:
            self.assertIn(f' neighbor {neighbor} priority {priority} poll-interval {poll_interval}', frrconfig) # default


    def test_ospf_07_passive_interface(self):
        self.session.set(base_path + ['passive-interface', 'default'])
        interfaces = Section.interfaces('ethernet')
        for interface in interfaces:
            self.session.set(base_path + ['passive-interface-exclude', interface])

        # commit changes
        self.session.commit()

        # Verify FRR ospfd configuration
        frrconfig = getFRROSPFconfig()
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' passive-interface default', frrconfig) # default
        for interface in interfaces:
            self.assertIn(f' no passive-interface {interface}', frrconfig) # default


    def test_ospf_08_redistribute(self):
        metric = '15'
        metric_type = '1'
        redistribute = ['bgp', 'connected', 'kernel', 'rip', 'static']

        for protocol in redistribute:
            self.session.set(base_path + ['redistribute', protocol, 'metric', metric])
            self.session.set(base_path + ['redistribute', protocol, 'route-map', route_map])
            if protocol not in ['kernel', 'static']:
                self.session.set(base_path + ['redistribute', protocol, 'metric-type', metric_type])

        # commit changes
        self.session.commit()

        # Verify FRR ospfd configuration
        frrconfig = getFRROSPFconfig()
        self.assertIn(f'router ospf', frrconfig)
        for protocol in redistribute:
            if protocol in ['kernel', 'static']:
                self.assertIn(f' redistribute {protocol} metric {metric} route-map {route_map}', frrconfig)
            else:
                self.assertIn(f' redistribute {protocol} metric {metric} metric-type {metric_type} route-map {route_map}', frrconfig)

    def test_ospf_09_virtual_link(self):
        networks = ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']
        area = '10'
        shortcut = 'enable'
        virtual_link = '192.0.2.1'
        hello = '6'
        retransmit = '5'
        transmit = '5'
        dead = '40'

        self.session.set(base_path + ['area', area, 'shortcut', shortcut])
        self.session.set(base_path + ['area', area, 'virtual-link', virtual_link, 'hello-interval', hello])
        self.session.set(base_path + ['area', area, 'virtual-link', virtual_link, 'retransmit-interval', retransmit])
        self.session.set(base_path + ['area', area, 'virtual-link', virtual_link, 'transmit-delay', transmit])
        self.session.set(base_path + ['area', area, 'virtual-link', virtual_link, 'dead-interval', dead])
        for network in networks:
            self.session.set(base_path + ['area', area, 'network', network])

        # commit changes
        self.session.commit()

        # Verify FRR ospfd configuration
        frrconfig = getFRROSPFconfig()
        self.assertIn(f'router ospf', frrconfig)
        self.assertIn(f' area {area} shortcut {shortcut}', frrconfig)
        self.assertIn(f' area {area} virtual-link {virtual_link} hello-interval {hello} retransmit-interval {retransmit} transmit-delay {transmit} dead-interval {dead}', frrconfig)
        for network in networks:
            self.assertIn(f' network {network} area {area}', frrconfig)

if __name__ == '__main__':
    unittest.main(verbosity=2)
