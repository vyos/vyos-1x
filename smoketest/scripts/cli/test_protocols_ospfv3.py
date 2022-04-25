#!/usr/bin/env python3
#
# Copyright (C) 2021-2022 VyOS maintainers and contributors
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
from vyos.util import process_named_running

PROCESS_NAME = 'ospf6d'
base_path = ['protocols', 'ospfv3']

route_map = 'foo-bar-baz-0815'

router_id = '192.0.2.1'
default_area = '0'

class TestProtocolsOSPFv3(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProtocolsOSPFv3, cls).setUpClass()

        cls.cli_set(cls, ['policy', 'route-map', route_map, 'rule', '10', 'action', 'permit'])
        cls.cli_set(cls, ['policy', 'route-map', route_map, 'rule', '20', 'action', 'permit'])

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['policy', 'route-map', route_map])
        super(TestProtocolsOSPFv3, cls).tearDownClass()

    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))
        self.cli_delete(base_path)
        self.cli_commit()

    def test_ospfv3_01_basic(self):
        seq = '10'
        prefix = '2001:db8::/32'
        acl_name = 'foo-acl-100'

        self.cli_set(['policy', 'access-list6', acl_name, 'rule', seq, 'action', 'permit'])
        self.cli_set(['policy', 'access-list6', acl_name, 'rule', seq, 'source', 'any'])

        self.cli_set(base_path + ['parameters', 'router-id', router_id])
        self.cli_set(base_path + ['area', default_area, 'range', prefix, 'advertise'])
        self.cli_set(base_path + ['area', default_area, 'export-list', acl_name])
        self.cli_set(base_path + ['area', default_area, 'import-list', acl_name])

        interfaces = Section.interfaces('ethernet')
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface, 'area', default_area])

        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf6', daemon='ospf6d')
        self.assertIn(f'router ospf6', frrconfig)
        self.assertIn(f' area {default_area} range {prefix}', frrconfig)
        self.assertIn(f' ospf6 router-id {router_id}', frrconfig)
        self.assertIn(f' area {default_area} import-list {acl_name}', frrconfig)
        self.assertIn(f' area {default_area} export-list {acl_name}', frrconfig)

        for interface in interfaces:
            if_config = self.getFRRconfig(f'interface {interface}', daemon='ospf6d')
            self.assertIn(f'ipv6 ospf6 area {default_area}', if_config)

        self.cli_delete(['policy', 'access-list6', acl_name])


    def test_ospfv3_02_distance(self):
        dist_global = '200'
        dist_external = '110'
        dist_inter_area = '120'
        dist_intra_area = '130'

        self.cli_set(base_path + ['distance', 'global', dist_global])
        self.cli_set(base_path + ['distance', 'ospfv3', 'external', dist_external])
        self.cli_set(base_path + ['distance', 'ospfv3', 'inter-area', dist_inter_area])
        self.cli_set(base_path + ['distance', 'ospfv3', 'intra-area', dist_intra_area])

        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf6', daemon='ospf6d')
        self.assertIn(f'router ospf6', frrconfig)
        self.assertIn(f' distance {dist_global}', frrconfig)
        self.assertIn(f' distance ospf6 intra-area {dist_intra_area} inter-area {dist_inter_area} external {dist_external}', frrconfig)


    def test_ospfv3_03_redistribute(self):
        route_map = 'foo-bar'
        route_map_seq = '10'
        redistribute = ['bgp', 'connected', 'kernel', 'ripng', 'static']

        self.cli_set(['policy', 'route-map', route_map, 'rule', route_map_seq, 'action', 'permit'])

        for protocol in redistribute:
            self.cli_set(base_path + ['redistribute', protocol, 'route-map', route_map])

        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf6', daemon='ospf6d')
        self.assertIn(f'router ospf6', frrconfig)
        for protocol in redistribute:
            self.assertIn(f' redistribute {protocol} route-map {route_map}', frrconfig)


    def test_ospfv3_04_interfaces(self):
        bfd_profile = 'vyos-ipv6'

        self.cli_set(base_path + ['parameters', 'router-id', router_id])
        self.cli_set(base_path + ['area', default_area])

        cost = '100'
        priority = '10'
        interfaces = Section.interfaces('ethernet')
        for interface in interfaces:
            if_base = base_path + ['interface', interface]
            self.cli_set(if_base + ['bfd', 'profile', bfd_profile])
            self.cli_set(if_base + ['cost', cost])
            self.cli_set(if_base + ['instance-id', '0'])
            self.cli_set(if_base + ['mtu-ignore'])
            self.cli_set(if_base + ['network', 'point-to-point'])
            self.cli_set(if_base + ['passive'])
            self.cli_set(if_base + ['priority', priority])
            cost = str(int(cost) + 10)
            priority = str(int(priority) + 5)

        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf6', daemon='ospf6d')
        self.assertIn(f'router ospf6', frrconfig)

        cost = '100'
        priority = '10'
        for interface in interfaces:
            if_config = self.getFRRconfig(f'interface {interface}', daemon='ospf6d')
            self.assertIn(f'interface {interface}', if_config)
            self.assertIn(f' ipv6 ospf6 bfd', if_config)
            self.assertIn(f' ipv6 ospf6 bfd profile {bfd_profile}', if_config)
            self.assertIn(f' ipv6 ospf6 cost {cost}', if_config)
            self.assertIn(f' ipv6 ospf6 mtu-ignore', if_config)
            self.assertIn(f' ipv6 ospf6 network point-to-point', if_config)
            self.assertIn(f' ipv6 ospf6 passive', if_config)
            self.assertIn(f' ipv6 ospf6 priority {priority}', if_config)
            cost = str(int(cost) + 10)
            priority = str(int(priority) + 5)


    def test_ospfv3_05_area_stub(self):
        area_stub = '23'
        area_stub_nosum = '26'

        self.cli_set(base_path + ['area', area_stub, 'area-type', 'stub'])
        self.cli_set(base_path + ['area', area_stub_nosum, 'area-type', 'stub', 'no-summary'])

        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf6', daemon='ospf6d')
        self.assertIn(f'router ospf6', frrconfig)
        self.assertIn(f' area {area_stub} stub', frrconfig)
        self.assertIn(f' area {area_stub_nosum} stub no-summary', frrconfig)


    def test_ospfv3_06_area_nssa(self):
        area_nssa = '1.1.1.1'
        area_nssa_nosum = '2.2.2.2'
        area_nssa_default = '3.3.3.3'

        self.cli_set(base_path + ['area', area_nssa, 'area-type', 'nssa'])
        self.cli_set(base_path + ['area', area_nssa, 'area-type', 'stub'])
        # can only set one area-type per OSPFv3 area
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['area', area_nssa, 'area-type', 'stub'])

        self.cli_set(base_path + ['area', area_nssa_nosum, 'area-type', 'nssa', 'no-summary'])
        self.cli_set(base_path + ['area', area_nssa_nosum, 'area-type', 'nssa', 'default-information-originate'])
        self.cli_set(base_path + ['area', area_nssa_default, 'area-type', 'nssa', 'default-information-originate'])

        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf6', daemon='ospf6d')
        self.assertIn(f'router ospf6', frrconfig)
        self.assertIn(f' area {area_nssa} nssa', frrconfig)
        self.assertIn(f' area {area_nssa_nosum} nssa default-information-originate no-summary', frrconfig)
        self.assertIn(f' area {area_nssa_default} nssa default-information-originate', frrconfig)


    def test_ospfv3_07_default_originate(self):
        seq = '100'
        metric = '50'
        metric_type = '1'

        self.cli_set(base_path + ['default-information', 'originate', 'metric', metric])
        self.cli_set(base_path + ['default-information', 'originate', 'metric-type', metric_type])
        self.cli_set(base_path + ['default-information', 'originate', 'route-map', route_map])

        # commit changes
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf6', daemon='ospf6d')
        self.assertIn(f'router ospf6', frrconfig)
        self.assertIn(f' default-information originate metric {metric} metric-type {metric_type} route-map {route_map}', frrconfig)

        # Now set 'always'
        self.cli_set(base_path + ['default-information', 'originate', 'always'])
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf6', daemon='ospf6d')
        self.assertIn(f' default-information originate always metric {metric} metric-type {metric_type} route-map {route_map}', frrconfig)


    def test_ospfv3_08_vrfs(self):
        # It is safe to assume that when the basic VRF test works, all
        # other OSPF related features work, as we entirely inherit the CLI
        # templates and Jinja2 FRR template.
        table = '1000'
        vrf = 'blue'
        vrf_base = ['vrf', 'name', vrf]
        vrf_iface = 'eth1'
        router_id = '1.2.3.4'
        router_id_vrf = '1.2.3.5'

        self.cli_set(vrf_base + ['table', table])
        self.cli_set(vrf_base + ['protocols', 'ospfv3', 'interface', vrf_iface, 'bfd'])
        self.cli_set(vrf_base + ['protocols', 'ospfv3', 'parameters', 'router-id', router_id_vrf])

        self.cli_set(['interfaces', 'ethernet', vrf_iface, 'vrf', vrf])

        # Also set a default VRF OSPF config
        self.cli_set(base_path + ['parameters', 'router-id', router_id])
        self.cli_commit()

        # Verify FRR ospfd configuration
        frrconfig = self.getFRRconfig('router ospf6', daemon='ospf6d')
        self.assertIn(f'router ospf6', frrconfig)
        self.assertIn(f' ospf6 router-id {router_id}', frrconfig)

        frrconfig = self.getFRRconfig(f'interface {vrf_iface}', daemon='ospf6d')
        self.assertIn(f'interface {vrf_iface}', frrconfig)
        self.assertIn(f' ipv6 ospf6 bfd', frrconfig)

        frrconfig = self.getFRRconfig(f'router ospf6 vrf {vrf}', daemon='ospf6d')
        self.assertIn(f'router ospf6 vrf {vrf}', frrconfig)
        self.assertIn(f' ospf6 router-id {router_id_vrf}', frrconfig)

        # cleanup
        self.cli_delete(['vrf', 'name', vrf])
        self.cli_delete(['interfaces', 'ethernet', vrf_iface, 'vrf'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
