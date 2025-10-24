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

import shutil
import unittest

from math import ceil
from time import sleep

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.utils.process import ip_cmd

vrf_base_path = ['vrf', 'name']
red = 'red-309aba83'
blue = 'blue-46b27cb'
used_vrf_names = [red, blue]
base_path = ['protocols', 'failover']

config_dir_root = '/run/vyos-failover.conf.d'

check_timeout = 1
wait_timeout = 5
wait_dhcp_timeout = 10

# Use numeric value to not get ip errors while
# /etc/iproute2/rt_protos.d/failover.conf is not installed yet
failover_protocol_value = 111

dummy_if1 = 'dum3711'
dummy_if2 = 'dum3712'
dummy_if3 = 'dum3713'

veth_if1 = 'veth71'
veth_if2 = 'veth72'

route_prefix = '203.0.113.0/24'
route2_prefix = '172.16.0.0/24'
route_base_path = base_path + ['route', route_prefix]

dummy_if1_addr = '192.168.30.1'
dummy_if2_addr = '10.0.70.1'
dummy_if3_addr = '10.20.0.1'

# These three must be in same subnet:
dhcp_prefix = '10.133.0'
veth_if1_addr = f'{dhcp_prefix}.1'
dhcp_gateway_addr_1 = f'{dhcp_prefix}.99'
dhcp_gateway_addr_2 = f'{dhcp_prefix}.117'


class RoutesChecker:
    def __init__(self, required_routes, allow_extra=False):
        self.required_routes = required_routes
        self.allow_extra = allow_extra
        self.error = ''

    def __call__(self, got_routes):
        self.error = ''
        if len(got_routes) < len(self.required_routes):
            self.error = f"Not enough routes: expected {len(self.required_routes)}, got {len(got_routes)}: {got_routes}"
            return False

        if not self.allow_extra and len(got_routes) != len(self.required_routes):
            self.error = f"Extra routes: expected {len(self.required_routes)}, got {len(got_routes)}: {got_routes}"

        for route in self.required_routes:
            found = False
            for got_route in got_routes:
                mismatch = False
                for key in route:
                    if route[key] is None:
                        if key in got_route:
                            mismatch = True
                            break
                    elif key not in got_route or got_route[key] != route[key]:
                        mismatch = True
                        break
                if not mismatch:
                    found = True
                    break
            if not found:
                self.error = f"Couldn't find required route {route} among received routes {got_routes}"
                return False
        return True


class TestProtocolsFailover(VyOSUnitTestSHIM.TestCase):
    def clean_and_stop_daemon(self):
        self.cli_delete(base_path)
        for vrf in used_vrf_names:
            self.cli_delete(vrf_base_path + [vrf] + base_path)
        self.cli_commit()
        shutil.rmtree(config_dir_root, ignore_errors=True)

    def setUp(self):
        # Needed dummy interfaces
        self.cli_set(['interfaces', 'dummy', dummy_if1])
        self.cli_set(['interfaces', 'dummy', dummy_if2])
        self.cli_set(['interfaces', 'dummy', dummy_if3])
        self.cli_set(
            ['interfaces', 'virtual-ethernet', veth_if1, 'peer-name', veth_if2]
        )
        self.cli_set(
            ['interfaces', 'virtual-ethernet', veth_if2, 'peer-name', veth_if1]
        )

        self.clean_and_stop_daemon()
        # always forward to base class
        super().setUp()

        self.clean_dhclient_lease_files = set()
        self.need_dhcp_dir_cleanup = False

    def tearDown(self):
        self.cli_delete(['interfaces', 'virtual-ethernet', veth_if2])
        self.cli_delete(['interfaces', 'virtual-ethernet', veth_if1])
        self.cli_delete(['interfaces', 'dummy', dummy_if3])
        self.cli_delete(['interfaces', 'dummy', dummy_if2])
        self.cli_delete(['interfaces', 'dummy', dummy_if1])
        self.cli_delete(['service', 'dhcp-server'])
        self.cli_delete(['service', 'dns'])

        self.clean_and_stop_daemon()

        failover_routes = ip_cmd(
            f'route show proto {failover_protocol_value} table all'
        )
        self.assertEqual(failover_routes, [], "Some failover IPv4 routes left")
        failover_routes = ip_cmd(
            f'-6 route show proto {failover_protocol_value} table all'
        )
        self.assertEqual(failover_routes, [], "Some failover IPv6 routes left")
        # always forward to base class
        super().tearDown()

    def wait_for_ip_output(self, ip_command_args, check, pause=0.1, timeout=3):
        tries = ceil(timeout / pause)
        result = None
        for i in range(tries):
            result = ip_cmd(ip_command_args)
            if callable(check):
                if check(result):
                    return True, result
            elif result == check:
                return True, result

            sleep(pause)

        return False, result

    def test_01_basic(self):
        res, output = self.wait_for_ip_output(
            f'route show proto {failover_protocol_value}',
            [],
            timeout=wait_timeout,
        )
        self.assertTrue(
            res, f"No failover routes must exist before test, last result: {output}"
        )

        self.cli_set(
            ['interfaces', 'dummy', dummy_if1, 'address', dummy_if1_addr + '/24']
        )
        self.cli_set(
            ['interfaces', 'dummy', dummy_if2, 'address', dummy_if2_addr + '/24']
        )
        self.cli_set(
            route_base_path + ['next-hop', dummy_if2_addr, 'interface', dummy_if2]
        )
        self.cli_set(route_base_path + ['next-hop', dummy_if2_addr, 'metric', '30'])
        self.cli_set(
            route_base_path
            + [
                'next-hop',
                dummy_if2_addr,
                'check',
                'target',
                dummy_if1_addr,
                'interface',
                dummy_if1,
            ]
        )
        self.cli_set(
            route_base_path
            + ['next-hop', dummy_if2_addr, 'check', 'timeout', str(check_timeout)]
        )
        self.cli_commit()

        # Now vyos-failover must be launched, it should create route, waiting for it...
        checker = RoutesChecker([{'dst': route_prefix}])
        res, output = self.wait_for_ip_output(
            f"route show proto {failover_protocol_value}",
            checker,
            timeout=wait_timeout,
        )
        self.assertTrue(res, f"Route must have been created, last result: {output}")

        self.cli_delete(['interfaces', 'dummy', dummy_if1, 'address'])
        self.cli_commit()

        res, output = self.wait_for_ip_output(
            f'route show proto {failover_protocol_value}',
            [],
            timeout=wait_timeout,
        )
        self.assertTrue(res, f"Route must have been deleted, last result: {output}")

    def test_02_vrf(self):
        # route 1 default VRF, check red
        # route 2 red, check blue
        # route 3 red, check red
        # route 1 and route 3 with same destination

        res, output = self.wait_for_ip_output(
            f'route show proto {failover_protocol_value} table all',
            [],
            timeout=wait_timeout,
        )
        self.assertTrue(
            res, f"No failover routes must exist before test, last result: {output}"
        )

        self.cli_set(['vrf', 'name', red, 'table', '43310'])
        self.cli_set(['vrf', 'name', blue, 'table', '43311'])

        self.cli_set(
            ['interfaces', 'dummy', dummy_if1, 'address', dummy_if1_addr + '/24']
        )
        self.cli_set(
            ['interfaces', 'dummy', dummy_if2, 'address', dummy_if2_addr + '/24']
        )
        self.cli_set(
            ['interfaces', 'dummy', dummy_if3, 'address', dummy_if3_addr + '/24']
        )
        self.cli_set(['interfaces', 'dummy', dummy_if2, 'vrf', red])
        self.cli_set(['interfaces', 'dummy', dummy_if3, 'vrf', blue])

        route_1_base = route_base_path
        route_2_base = vrf_base_path + [red] + base_path + ['route', route2_prefix]
        route_3_base = vrf_base_path + [red] + base_path + ['route', route_prefix]

        self.cli_set(
            route_1_base + ['next-hop', dummy_if1_addr, 'interface', dummy_if1]
        )
        self.cli_set(
            route_1_base
            + [
                'next-hop',
                dummy_if1_addr,
                'check',
                'target',
                dummy_if2_addr,
                'vrf',
                red,
            ]
        )
        self.cli_set(
            route_1_base
            + ['next-hop', dummy_if1_addr, 'check', 'timeout', str(check_timeout)]
        )

        self.cli_set(
            route_2_base + ['next-hop', dummy_if2_addr, 'interface', dummy_if2]
        )
        self.cli_set(
            route_2_base
            + [
                'next-hop',
                dummy_if2_addr,
                'check',
                'target',
                dummy_if3_addr,
                'vrf',
                blue,
            ]
        )
        self.cli_set(
            route_2_base
            + ['next-hop', dummy_if2_addr, 'check', 'timeout', str(check_timeout)]
        )

        self.cli_set(
            route_3_base + ['next-hop', dummy_if2_addr, 'interface', dummy_if2]
        )
        self.cli_set(
            route_3_base
            + [
                'next-hop',
                dummy_if2_addr,
                'check',
                'target',
                dummy_if2_addr,
            ]
        )
        self.cli_set(
            route_3_base
            + ['next-hop', dummy_if2_addr, 'check', 'timeout', str(check_timeout)]
        )

        self.cli_commit()

        route1_fields = {'dst': route_prefix, 'gateway': dummy_if1_addr, 'table': None}
        route2_fields = {
            'dst': route2_prefix,
            'gateway': dummy_if2_addr,
            'table': red,
        }
        route3_fields = {'dst': route_prefix, 'gateway': dummy_if2_addr, 'table': red}

        # All three routes must be created
        checker1 = RoutesChecker([route1_fields, route2_fields, route3_fields])
        res, output = self.wait_for_ip_output(
            f"route show proto {failover_protocol_value} table all",
            checker1,
            timeout=wait_timeout * 3,
        )
        self.assertTrue(
            res, f"Routes must have been created, checker error: {checker1.error}"
        )

        # Delete dummy_if3, route2 must be deleted
        self.cli_delete(['interfaces', 'dummy', dummy_if3, 'address'])
        self.cli_commit()

        checker2 = RoutesChecker([route1_fields, route3_fields])
        res, output = self.wait_for_ip_output(
            f'route show proto {failover_protocol_value} table all',
            checker2,
            timeout=wait_timeout * 3,
        )
        self.assertTrue(
            res,
            f"Only route1 and route3 must have been left, checker error: {checker2.error}",
        )

        # Delete dummy_if2, all routes must be deleted
        self.cli_delete(['interfaces', 'dummy', dummy_if2, 'address'])
        self.cli_commit()
        res, output = self.wait_for_ip_output(
            f'route show proto {failover_protocol_value} table all',
            [],
            timeout=wait_timeout * 3,
        )
        self.assertTrue(res, f"No routes should have been left, got: {output}")

    def test_03_config(self):
        # Test how daemon reacts to routes add/delete, files add/delete
        # All checks in this test are always true, configuration is added/deleted only

        # route 1 default VRF
        # route 2 default VRF
        # route 3 red
        route1_fields = {'dst': route_prefix, 'gateway': dummy_if1_addr, 'table': None}
        route2_fields = {'dst': route2_prefix, 'gateway': dummy_if1_addr, 'table': None}
        route3_fields = {'dst': route_prefix, 'gateway': dummy_if2_addr, 'table': red}

        res, output = self.wait_for_ip_output(
            f'route show proto {failover_protocol_value} table all',
            [],
            timeout=wait_timeout,
        )
        self.assertTrue(
            res, f"No failover routes must exist before test, last result: {output}"
        )

        self.cli_set(['vrf', 'name', red, 'table', '43310'])
        self.cli_set(['vrf', 'name', blue, 'table', '43311'])

        self.cli_set(
            ['interfaces', 'dummy', dummy_if1, 'address', dummy_if1_addr + '/24']
        )
        self.cli_set(
            ['interfaces', 'dummy', dummy_if2, 'address', dummy_if2_addr + '/24']
        )
        self.cli_set(['interfaces', 'dummy', dummy_if2, 'vrf', red])

        route_1_base = route_base_path
        route_2_base = base_path + ['route', route2_prefix]
        route_3_base = vrf_base_path + [red] + base_path + ['route', route_prefix]

        self.cli_set(
            route_1_base + ['next-hop', dummy_if1_addr, 'interface', dummy_if1]
        )
        self.cli_set(
            route_1_base
            + [
                'next-hop',
                dummy_if1_addr,
                'check',
                'target',
                dummy_if1_addr,
            ]
        )
        self.cli_set(
            route_1_base
            + ['next-hop', dummy_if1_addr, 'check', 'timeout', str(check_timeout)]
        )
        self.cli_commit()

        # Adding only route1
        checker1 = RoutesChecker([route1_fields])
        res, output = self.wait_for_ip_output(
            f"route show proto {failover_protocol_value} table all",
            checker1,
            timeout=wait_timeout * 3,
        )
        self.assertTrue(
            res, f"Route 1 must have been created, checker error: {checker1.error}"
        )

        # adding route 3 - new file
        self.cli_set(
            route_3_base + ['next-hop', dummy_if2_addr, 'interface', dummy_if2]
        )
        self.cli_set(
            route_3_base
            + [
                'next-hop',
                dummy_if2_addr,
                'check',
                'target',
                dummy_if2_addr,
            ]
        )
        self.cli_set(
            route_3_base
            + ['next-hop', dummy_if2_addr, 'check', 'timeout', str(check_timeout)]
        )
        self.cli_commit()

        # Now route1 and route3 must be active
        checker13 = RoutesChecker([route1_fields, route3_fields])
        res, output = self.wait_for_ip_output(
            f"route show proto {failover_protocol_value} table all",
            checker13,
            timeout=wait_timeout * 3,
        )
        self.assertTrue(
            res,
            f"Route 1 and route 3 must have been created, checker error: {checker13.error}",
        )

        # Now add route2 (add of route to file)
        self.cli_set(
            route_2_base + ['next-hop', dummy_if1_addr, 'interface', dummy_if1]
        )
        self.cli_set(
            route_2_base
            + [
                'next-hop',
                dummy_if1_addr,
                'check',
                'target',
                dummy_if1_addr,
            ]
        )
        self.cli_set(
            route_2_base
            + ['next-hop', dummy_if1_addr, 'check', 'timeout', str(check_timeout)]
        )
        self.cli_commit()

        # All three routes must be created
        checker123 = RoutesChecker([route1_fields, route2_fields, route3_fields])
        res, output = self.wait_for_ip_output(
            f'route show proto {failover_protocol_value} table all',
            checker123,
            timeout=wait_timeout * 3,
        )
        self.assertTrue(
            res,
            f"All three routes must have been created, checker error: {checker123.error}",
        )

        # Delete route1
        self.cli_delete(route_1_base)
        self.cli_commit()

        # Now route2 and route3 must be active
        checker23 = RoutesChecker([route2_fields, route3_fields])
        res, output = self.wait_for_ip_output(
            f"route show proto {failover_protocol_value} table all",
            checker23,
            timeout=wait_timeout * 3,
        )
        self.assertTrue(
            res,
            f"Route 1 must have been deleted, routes 2 and 3 active. Checker error: {checker23.error}",
        )

        # Delete route2 - file deletion
        self.cli_delete(route_2_base)
        self.cli_commit()

        # Now only route3 must be active
        checker3 = RoutesChecker([route3_fields])
        res, output = self.wait_for_ip_output(
            f"route show proto {failover_protocol_value} table all",
            checker3,
            timeout=wait_timeout * 3,
        )
        self.assertTrue(
            res,
            f"Route 2 must have been deleted, only routes 3 should be active. Checker error: {checker3.error}",
        )

        # Deleting last route
        self.cli_delete(route_3_base)
        self.cli_commit()

        res, output = self.wait_for_ip_output(
            f'route show proto {failover_protocol_value} table all',
            [],
            timeout=wait_timeout * 3,
        )
        self.assertTrue(res, f"No routes should have been left, got: {output}")


    def test_04_dhcp(self):
        res, output = self.wait_for_ip_output(
            f'route show proto {failover_protocol_value}',
            [],
            timeout=wait_timeout,
        )
        self.assertTrue(
            res, f"No failover routes must exist before test, last result: {output}"
        )

        # Setup DHCP server
        self.cli_set(
            [
                'interfaces',
                'virtual-ethernet',
                veth_if1,
                'address',
                f'{dhcp_prefix}.1/24',
            ]
        )
        self.cli_set(['interfaces', 'virtual-ethernet', veth_if1, 'description', 'LAN'])

        service_base = [
            'service',
            'dhcp-server',
            'shared-network-name',
            'LAN',
            'subnet',
            f'{dhcp_prefix}.0/24',
        ]
        self.cli_set(service_base + ['option', 'name-server', f'{dhcp_prefix}.1'])
        self.cli_set(service_base + ['option', 'domain-name', 'vyos'])
        self.cli_set(service_base + ['lease', '86400'])
        self.cli_set(service_base + ['range', '0', 'start', f'{dhcp_prefix}.9'])
        self.cli_set(service_base + ['range', '0', 'stop', f'{dhcp_prefix}.254'])
        self.cli_set(service_base + ['subnet-id', '1952'])

        self.cli_set(['service', 'dns', 'forwarding', 'cache-size', '0'])
        self.cli_set(
            ['service', 'dns', 'forwarding', 'listen-address', f'{dhcp_prefix}.1']
        )
        self.cli_set(
            ['service', 'dns', 'forwarding', 'allow-from', f'{dhcp_prefix}.0/24']
        )
        # End setup DHCP server

        # Setting first DHCP Gateway address
        self.cli_set(service_base + ['option', 'default-router', dhcp_gateway_addr_1])

        self.cli_set(
            ['interfaces', 'dummy', dummy_if1, 'address', dummy_if1_addr + '/24']
        )
        self.cli_set(
            ['interfaces', 'dummy', dummy_if2, 'address', dummy_if2_addr + '/24']
        )
        self.cli_set(['interfaces', 'virtual-ethernet', veth_if2, 'address', 'dhcp'])
        self.cli_set(route_base_path + ['dhcp-interface', veth_if2])
        base_dhcp_interface = route_base_path + ['dhcp-interface', veth_if2]
        self.cli_set(base_dhcp_interface + ['metric', '30'])
        self.cli_set(
            base_dhcp_interface
            + [
                'check',
                'target',
                dummy_if1_addr,
                'interface',
                dummy_if1,
            ]
        )
        self.cli_set(base_dhcp_interface + ['check', 'timeout', str(check_timeout)])
        self.cli_commit()

        # Now vyos-failover must be launched, it should create route to first dhcp address
        checker = RoutesChecker([{'dst': route_prefix, 'gateway': dhcp_gateway_addr_1}])
        res, output = self.wait_for_ip_output(
            f"route show proto {failover_protocol_value}",
            checker,
            timeout=wait_dhcp_timeout,
        )
        self.assertTrue(
            res,
            f"Route must have been created via fist dhcp address. Checker error: {checker.error}",
        )

        # Change DHCP gateway address
        renew_cmd = ['renew', 'dhcp', 'interface', veth_if2]
        self.cli_set(service_base + ['option', 'default-router', dhcp_gateway_addr_2])
        self.cli_commit()
        self.op_mode(renew_cmd)

        checker = RoutesChecker([{'dst': route_prefix, 'gateway': dhcp_gateway_addr_2}])
        res, output = self.wait_for_ip_output(
            f"route show proto {failover_protocol_value}",
            checker,
            timeout=wait_dhcp_timeout,
        )
        self.assertTrue(
            res,
            f"Route must have been created via second dhcp address. Checker error: {checker.error}",
        )

        # DHCP server down
        self.cli_delete(['service', 'dhcp-server'])
        self.cli_delete(['service', 'dns'])
        self.cli_commit()
        self.op_mode(renew_cmd)

        res, output = self.wait_for_ip_output(
            f'route show proto {failover_protocol_value}',
            [],
            timeout=wait_dhcp_timeout,
        )
        self.assertTrue(res, f"Route must have been deleted, last result: {output}")


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
