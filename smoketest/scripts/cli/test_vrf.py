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

import re
import os
import unittest

from json import loads
from jmespath import search

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Interface
from vyos.ifconfig import Section
from vyos.utils.file import read_file
from vyos.utils.misc import wait_for
from vyos.utils.network import get_interface_config
from vyos.utils.network import get_nft_vrf_zone_mapping
from vyos.utils.network import get_vrf_tableid
from vyos.utils.network import is_intf_addr_assigned
from vyos.utils.network import interface_exists
from subprocess import DEVNULL
from subprocess import STDOUT

from vyos.utils.process import cmdl
from vyos.utils.system import sysctl_read
from vyos.template import inc_ip
from vyos.utils.process import process_named_running
from vyos.xml_ref import default_value

base_path = ['vrf']
vrfs = ['red', 'green', 'blue', 'foo-bar', 'baz_foo']
v4_protocols = ['any', 'babel', 'bgp', 'eigrp', 'isis', 'ospf', 'rip', 'static']
v6_protocols = ['any', 'babel', 'bgp', 'isis', 'ospfv3', 'ripng', 'static']

def dad_completed(interface: str) -> bool:
    """
    True once no address of the interface is tentative any more. An IPv6
    address can not be used as a source until duplicate address detection
    finished. "ip link show" carries no address at all, it has to be
    "ip addr show".
    """
    tmp = loads(cmdl(['ip', '--json', 'addr', 'show', 'dev', interface]))
    return not any(addr.get('tentative', False)
                   for addr in tmp[0].get('addr_info', []))

def ping_in_vrf(vrf: str, destination: str, message: str) -> None:
    """
    Ping from within a VRF and fail the test if nothing comes back. The
    smoketests do not run as root, and popen() refuses its vrf= argument to an
    unprivileged user, so the VRF is entered by way of sudo(8) instead.
    """
    cmdl(['ip', 'vrf', 'exec', vrf, 'ping', '-c', '3', '-W', '1', destination],
         sudo=True, stderr=STDOUT, raising=AssertionError, message=message)

def get_conntrack_entries() -> str:
    """
    Full conntrack table, used to verify the zone assignment and that a flow
    actually got a reply (an unmatched flow is shown as [UNREPLIED])
    """
    return cmdl(['conntrack', '-L'], sudo=True, stderr=DEVNULL)

def get_conntrack_insert_failed() -> int:
    """
    Sum of the per CPU conntrack insert_failed counters. Every conntrack entry
    that can not be inserted - e.g. because its reply tuple is already taken -
    increments this counter and the packet is dropped.
    """
    tmp = cmdl(['conntrack', '-S'], sudo=True)
    return sum(int(count) for count in re.findall(r'insert_failed=(\d+)', tmp))

class VRFTest(VyOSUnitTestSHIM.TestCase):
    _interfaces = []

    @classmethod
    def setUpClass(cls):
        # we need to filter out VLAN interfaces identified by a dot (.)
        # in their name - just in case!
        if 'TEST_ETH' in os.environ:
            tmp = os.environ['TEST_ETH'].split()
            cls._interfaces = tmp
        else:
            for tmp in Section.interfaces('ethernet', vlan=False):
                cls._interfaces.append(tmp)

        # call base-classes classmethod
        super(VRFTest, cls).setUpClass()

    def setUp(self):
        # always forward to base class
        super().setUp()

        # Interfaces a test created and which must go away before the VRFs they
        # are enslaved to can be removed
        self._cleanup_interfaces = []
        self._cleanup_netns = []
        # Configuration outside the vrf tree a test created. It has to go in the
        # same commit that removes the VRFs, as it can reference both them and
        # the interfaces enslaved to them
        self._cleanup_paths = []

        # VRF strict_most is always enabled
        tmp = read_file('/proc/sys/net/vrf/strict_mode')
        self.assertEqual(tmp, '1')

    def tearDown(self):
        # A VRF can not be removed while it still has member interfaces, so get
        # rid of them first - also on the way out of a failed test
        # An interface that was moved into a netns has to come back first -
        # VyOS can not remove a veth pair with one end in another namespace
        for netns, interface in self._cleanup_netns:
            cmdl(['ip', 'netns', 'exec', netns, 'ip', 'link', 'set', interface,
                  'netns', '1'], sudo=True, expect=[0, 1])
            cmdl(['ip', 'netns', 'delete', netns], sudo=True, expect=[0, 1])
        for path in self._cleanup_paths:
            self.cli_delete(path)
        for interface in self._cleanup_interfaces:
            self.cli_delete(['interfaces', 'virtual-ethernet', interface])
        # delete all VRFs
        self.cli_delete(base_path)
        self.cli_commit()

        for vrf in vrfs:
            self.assertFalse(interface_exists(vrf))
        # always forward to base class
        super().tearDown()

    def walk_path(self, obj, path):
        current = obj

        for i, key in enumerate(path):
            if isinstance(key, str):
                self.assertTrue(isinstance(current, dict), msg=f'Failed path: {path}')
                self.assertTrue(key in current, msg=f'Failed path: {path}')
            elif isinstance(key, int):
                self.assertTrue(isinstance(current, list), msg=f'Failed path: {path}')
                self.assertTrue(0 <= key < len(current), msg=f'Failed path: {path}')
            else:
                assert False, 'Invalid type'

            current = current[key]

        return current

    def verify_config_object(self, obj, path, value):
        base_obj = self.walk_path(obj, path)
        self.assertTrue(isinstance(base_obj, list))
        self.assertTrue(any(True for v in base_obj if v == value))

    def verify_config_value(self, obj, path, key, value):
        base_obj = self.walk_path(obj, path)
        if isinstance(base_obj, list):
            self.assertTrue(any(True for v in base_obj if key in v and v[key] == value))
        elif isinstance(base_obj, dict):
            self.assertTrue(key in base_obj)
            self.assertEqual(base_obj[key], value)

    def verify_kea_service_running(self, process_name):
        tmp = cmdl(['tail', '-n', '100', '/var/log/messages'])
        self.assertTrue(
            process_named_running(process_name), msg=f'Service not running, log: {tmp}'
        )

    def test_vrf_vni_and_table_id(self):
        base_table = '1000'
        table = base_table
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            description = f'VyOS-VRF-{vrf}'
            self.cli_set(base + ['description', description])

            # check validate() - a table ID is mandatory
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()

            self.cli_set(base + ['table', table])
            self.cli_set(base + ['vni', table])
            if vrf == 'green':
                self.cli_set(base + ['disable'])

            table = str(int(table) + 1)

        # commit changes
        self.cli_commit()

        # Verify VRF configuration
        table = base_table
        iproute2_config = read_file('/etc/iproute2/rt_tables.d/vyos-vrf.conf')
        for vrf in vrfs:
            description = f'VyOS-VRF-{vrf}'
            self.assertTrue(interface_exists(vrf))
            vrf_if = Interface(vrf)
            # validate proper interface description
            self.assertEqual(vrf_if.get_alias(), description)
            # validate admin up/down state of VRF
            state = 'up'
            if vrf == 'green':
                state = 'down'
            self.assertEqual(vrf_if.get_admin_state(), state)

            # Test the iproute2 lookup file, syntax is as follows:
            #
            # # id       vrf name         comment
            # 1000       red              # VyOS-VRF-red
            # 1001       green            # VyOS-VRF-green
            #  ...
            regex = f'{table}\s+{vrf}\s+#\s+{description}'
            self.assertTrue(re.findall(regex, iproute2_config))

            frrconfig = self.getFRRconfig(f'vrf {vrf}', stop_section='^exit-vrf')
            self.assertIn(f' vni {table}', frrconfig)

            self.assertEqual(int(table), get_vrf_tableid(vrf))

            # Increment table ID for the next run
            table = str(int(table) + 1)

    def test_vrf_loopbacks_ips(self):
        table = '2000'
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_set(base + ['table', str(table)])
            table = str(int(table) + 1)

        # commit changes
        self.cli_commit()

        # Verify VRF configuration
        loopbacks = ['127.0.0.1', '::1']
        for vrf in vrfs:
            # Ensure VRF was created
            self.assertTrue(interface_exists(vrf))
            # Verify IP forwarding is 1 (enabled)
            self.assertEqual(sysctl_read(['net', 'ipv4', 'conf', vrf, 'forwarding']), '1')
            self.assertEqual(sysctl_read(['net', 'ipv6', 'conf', vrf, 'forwarding']), '1')

            # Test for proper loopback IP assignment
            for addr in loopbacks:
                self.assertTrue(is_intf_addr_assigned(vrf, addr))

    def test_vrf_bind_all(self):
        table = '2000'
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_set(base + ['table', str(table)])
            table = str(int(table) + 1)

        self.cli_set(base_path +  ['bind-to-all'])

        # commit changes
        self.cli_commit()

        # Verify VRF configuration
        self.assertEqual(sysctl_read(['net', 'ipv4', 'tcp_l3mdev_accept']), '1')
        self.assertEqual(sysctl_read(['net', 'ipv4', 'udp_l3mdev_accept']), '1')

        # If there is any VRF defined, strict_mode should be on
        self.assertEqual(sysctl_read(['net', 'vrf', 'strict_mode']), '1')

    def test_vrf_table_id_is_unalterable(self):
        # Linux Kernel prohibits the change of a VRF table  on the fly.
        # VRF must be deleted and recreated!
        table = '1000'
        vrf = vrfs[0]
        base = base_path + ['name', vrf]
        self.cli_set(base + ['table', table])

        # commit changes
        self.cli_commit()

        # Check if VRF has been created
        self.assertTrue(interface_exists(vrf))

        table = str(int(table) + 1)
        self.cli_set(base + ['table', table])
        # check validate() - table ID cannot be altered!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

    def test_vrf_assign_interface(self):
        vrf = vrfs[0]
        table = '5000'
        self.cli_set(['vrf', 'name', vrf, 'table', table])

        for interface in self._interfaces:
            section = Section.section(interface)
            self.cli_set(['interfaces', section, interface, 'vrf', vrf])

        # commit changes
        self.cli_commit()

        # Verify VRF assignmant
        for interface in self._interfaces:
            tmp = get_interface_config(interface)
            self.assertEqual(vrf, tmp['master'])

            # cleanup
            section = Section.section(interface)
            self.cli_delete(['interfaces', section, interface, 'vrf'])

    def test_vrf_static_route(self):
        base_table = '100'
        table = base_table
        for vrf in vrfs:
            next_hop = f'192.0.{table}.1'
            prefix = f'10.0.{table}.0/24'
            base = base_path + ['name', vrf]

            self.cli_set(base + ['vni', table])

            # check validate() - a table ID is mandatory
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()

            self.cli_set(base + ['table', table])
            self.cli_set(base + ['protocols', 'static', 'route', prefix, 'next-hop', next_hop])

            table = str(int(table) + 1)

        # commit changes
        self.cli_commit()

        # Verify VRF configuration
        table = base_table
        for vrf in vrfs:
            next_hop = f'192.0.{table}.1'
            prefix = f'10.0.{table}.0/24'

            self.assertTrue(interface_exists(vrf))

            frrconfig = self.getFRRconfig(f'vrf {vrf}', stop_section='^exit-vrf')
            self.assertIn(f' vni {table}', frrconfig)
            self.assertIn(f' ip route {prefix} {next_hop}', frrconfig)

            # Increment table ID for the next run
            table = str(int(table) + 1)

    def test_vrf_link_local_ip_addresses(self):
        # Testcase for issue T4331
        table = '100'
        vrf = 'orange'
        interface = 'dum9998'
        addresses = ['192.0.2.1/26', '2001:db8:9998::1/64', 'fe80::1/64']

        for address in addresses:
            self.cli_set(['interfaces', 'dummy', interface, 'address', address])

        # Create dummy interfaces
        self.cli_commit()

        # ... and verify IP addresses got assigned
        for address in addresses:
            self.assertTrue(is_intf_addr_assigned(interface, address))

        # Move interface to VRF
        self.cli_set(base_path + ['name', vrf, 'table', table])
        self.cli_set(['interfaces', 'dummy', interface, 'vrf', vrf])

        # Apply VRF config
        self.cli_commit()
        # Ensure VRF got created
        self.assertTrue(interface_exists(vrf))
        # ... and IP addresses are still assigned
        for address in addresses:
            self.assertTrue(is_intf_addr_assigned(interface, address))
        # Verify VRF table ID
        self.assertEqual(int(table), get_vrf_tableid(vrf))

        # Verify interface is assigned to VRF
        tmp = get_interface_config(interface)
        self.assertEqual(vrf, tmp['master'])

        # Delete Interface
        self.cli_delete(['interfaces', 'dummy', interface])
        self.cli_commit()

    def test_delete_vrf_protocols_should_not_crash(self):
        # Testcase for issue T7255:
        #   - verify that deleting the 'protocols' node under a VRF does not crash.

        table = '3000'
        vrf = 'purple'
        interface = 'dum3000'
        router_id = '10.2.0.2'

        # Configure dummy interface and assign to VRF
        self.cli_set(['interfaces', 'dummy', interface, 'address', '10.1.0.254/24'])
        self.cli_set(['interfaces', 'dummy', interface, 'vrf', vrf])

        # Configure OSPF under the VRF
        base_ospf_path = base_path + ['name', vrf, 'protocols', 'ospf']
        self.cli_set(base_ospf_path + ['interface', interface, 'area', '0'])
        self.cli_set(base_ospf_path + ['parameters', 'router-id', router_id])
        self.cli_set(['protocols', 'ospf'])

        # Assign routing table number to the VRF
        self.cli_set(base_path + ['name', vrf, 'table', table])

        # Commit configuration and verify VRF was successfully created
        self.cli_commit()
        self.assertTrue(interface_exists(vrf))
        frrconfig = self.getFRRconfig(f'router ospf vrf {vrf}', stop_section='^exit')
        self.assertIn(f'ospf router-id {router_id}', frrconfig)

        try:
            # Attempt to delete the entire 'protocols' subtree under VRF
            self.cli_delete(base_path + ['name', vrf, 'protocols'])
            self.cli_commit()

            # Verify result of deleting 'protocols' subtree
            frrconfig = self.getFRRconfig(f'router ospf vrf {vrf}', stop_section='^exit')
            self.assertNotIn(f'ospf router-id {router_id}', frrconfig)
        finally:
            # Clean up dummy interface and VRF and re-commit
            self.cli_delete(['interfaces', 'dummy', interface])
            self.cli_delete(base_path + ['name', vrf])
            self.cli_commit()

    def test_vrf_disable_forwarding(self):
        table = '2000'
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_set(base + ['table', table])
            self.cli_set(base + ['ip', 'disable-forwarding'])
            self.cli_set(base + ['ipv6', 'disable-forwarding'])
            table = str(int(table) + 1)

        # commit changes
        self.cli_commit()

        # Verify VRF configuration
        loopbacks = ['127.0.0.1', '::1']
        for vrf in vrfs:
            # Ensure VRF was created
            self.assertTrue(interface_exists(vrf))
            # Verify IP forwarding is 0 (disabled)
            self.assertEqual(sysctl_read(['net', 'ipv4', 'conf', vrf, 'forwarding']), '0')
            self.assertEqual(sysctl_read(['net', 'ipv6', 'conf', vrf, 'forwarding']), '0')

    def test_vrf_ip_protocol_route_map(self):
        table = '6000'

        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_set(base + ['table', table])

            for protocol in v4_protocols:
                self.cli_set(['policy', 'route-map', f'route-map-{vrf}-{protocol}', 'rule', '10', 'action', 'permit'])
                self.cli_set(base + ['ip', 'protocol', protocol, 'route-map', f'route-map-{vrf}-{protocol}'])

            table = str(int(table) + 1)

        self.cli_commit()

        # Verify route-map properly applied to FRR
        for vrf in vrfs:
            frrconfig = self.getFRRconfig(f'vrf {vrf}', stop_section='^exit-vrf')
            self.assertIn(f'vrf {vrf}', frrconfig)
            for protocol in v4_protocols:
                self.assertIn(f' ip protocol {protocol} route-map route-map-{vrf}-{protocol}', frrconfig)

        # Delete route-maps
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_delete(['policy', 'route-map', f'route-map-{vrf}-{protocol}'])
            self.cli_delete(base + ['ip', 'protocol'])

        self.cli_commit()

        # Verify route-map properly is removed from FRR
        for vrf in vrfs:
            frrconfig = self.getFRRconfig(f'vrf {vrf}', stop_section='^exit-vrf')
            self.assertNotIn(f' ip protocol', frrconfig)

    def test_vrf_ip_ipv6_protocol_non_existing_route_map(self):
        table = '6100'
        non_existing = 'non-existing'

        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_set(base + ['table', table])
            for protocol in v4_protocols:
                self.cli_set(base + ['ip', 'protocol', protocol, 'route-map', f'v4-{non_existing}'])
            for protocol in v6_protocols:
                self.cli_set(base + ['ipv6', 'protocol', protocol, 'route-map', f'v6-{non_existing}'])

            table = str(int(table) + 1)

        # Both v4 and v6 route-maps do not exist yet
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(['policy', 'route-map', f'v4-{non_existing}', 'rule', '10', 'action', 'deny'])

        # v6 route-map does not exist yet
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(['policy', 'route-map', f'v6-{non_existing}', 'rule', '10', 'action', 'deny'])

        # Commit again
        self.cli_commit()

    def test_vrf_ipv6_protocol_route_map(self):
        table = '6200'

        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_set(base + ['table', table])

            for protocol in v6_protocols:
                route_map = f'route-map-{vrf}-{protocol.replace("ospfv3", "ospf6")}'
                self.cli_set(['policy', 'route-map', route_map, 'rule', '10', 'action', 'permit'])
                self.cli_set(base + ['ipv6', 'protocol', protocol, 'route-map', route_map])

            table = str(int(table) + 1)

        self.cli_commit()

        # Verify route-map properly applied to FRR
        for vrf in vrfs:
            frrconfig = self.getFRRconfig(f'vrf {vrf}', stop_section='^exit-vrf')
            self.assertIn(f'vrf {vrf}', frrconfig)
            for protocol in v6_protocols:
                # VyOS and FRR use a different name for OSPFv3 (IPv6)
                if protocol == 'ospfv3':
                    protocol = 'ospf6'
                route_map = f'route-map-{vrf}-{protocol}'
                self.assertIn(f' ipv6 protocol {protocol} route-map {route_map}', frrconfig)

        # Delete route-maps
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_delete(['policy', 'route-map', f'route-map-{vrf}-{protocol}'])
            self.cli_delete(base + ['ipv6', 'protocol'])

        self.cli_commit()

        # Verify route-map properly is removed from FRR
        for vrf in vrfs:
            frrconfig = self.getFRRconfig(f'vrf {vrf}', stop_section='^exit-vrf')
            self.assertNotIn(f' ipv6 protocol', frrconfig)

    def test_vrf_vni_duplicates(self):
        base_table = '6300'
        table = base_table
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_set(base + ['table', str(table)])
            self.cli_set(base + ['vni', '100'])
            table = str(int(table) + 1)

        # L3VNIs can only be used once
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        table = base_table
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_set(base + ['vni', str(table)])
            table = str(int(table) + 1)

        # commit changes
        self.cli_commit()

        # Verify VRF configuration
        table = base_table
        for vrf in vrfs:
            self.assertTrue(interface_exists(vrf))

            frrconfig = self.getFRRconfig(f'vrf {vrf}', stop_section='^exit-vrf')
            self.assertIn(f' vni {table}', frrconfig)
            # Increment table ID for the next run
            table = str(int(table) + 1)

    def test_vrf_vni_add_change_remove(self):
        base_table = '6300'
        table = base_table
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_set(base + ['table', str(table)])
            self.cli_set(base + ['vni', str(table)])
            table = str(int(table) + 1)

        # commit changes
        self.cli_commit()

        # Verify VRF configuration
        table = base_table
        for vrf in vrfs:
            self.assertTrue(interface_exists(vrf))

            frrconfig = self.getFRRconfig(f'vrf {vrf}', stop_section='^exit-vrf')
            self.assertIn(f' vni {table}', frrconfig)
            # Increment table ID for the next run
            table = str(int(table) + 1)

        # Now change all L3VNIs (increment 2)
        # We must also change the base_table number as we probably could get
        # duplicate VNI's during the test as VNIs are applied 1:1 to FRR
        base_table = '5000'
        table = base_table
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_set(base + ['vni', str(table)])
            table = str(int(table) + 2)

        # commit changes
        self.cli_commit()

        # Verify VRF configuration
        table = base_table
        for vrf in vrfs:
            self.assertTrue(interface_exists(vrf))

            frrconfig = self.getFRRconfig(f'vrf {vrf}', stop_section='^exit-vrf')
            self.assertIn(f' vni {table}', frrconfig)
            # Increment table ID for the next run
            table = str(int(table) + 2)


        # add a new VRF with VNI - this must not delete any existing VRF/VNI
        purple = 'purple'
        table = str(int(table) + 10)
        self.cli_set(base_path + ['name', purple, 'table', table])
        self.cli_set(base_path + ['name', purple, 'vni', table])

        # commit changes
        self.cli_commit()

        # Verify VRF configuration
        table = base_table
        for vrf in vrfs:
            self.assertTrue(interface_exists(vrf))

            frrconfig = self.getFRRconfig(f'vrf {vrf}', stop_section='^exit-vrf')
            self.assertIn(f' vni {table}', frrconfig)
            # Increment table ID for the next run
            table = str(int(table) + 2)

        # Verify purple VRF/VNI
        self.assertTrue(interface_exists(purple))
        table = str(int(table) + 10)
        frrconfig = self.getFRRconfig(f'vrf {purple}', stop_section='^exit-vrf')
        self.assertIn(f' vni {table}', frrconfig)

        # Now delete all the VNIs
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_delete(base + ['vni'])

        # commit changes
        self.cli_commit()

        # Verify no VNI is defined
        for vrf in vrfs:
            self.assertTrue(interface_exists(vrf))

            frrconfig = self.getFRRconfig(f'vrf {vrf}', stop_section='^exit-vrf')
            self.assertNotIn('vni', frrconfig)

        # Verify purple VNI remains
        self.assertTrue(interface_exists(purple))
        frrconfig = self.getFRRconfig(f'vrf {purple}', stop_section='^exit-vrf')
        self.assertIn(f' vni {table}', frrconfig)

    def test_vrf_ip_ipv6_nht(self):
        table = '6910'

        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_set(base + ['table', table])
            self.cli_set(base + ['ip', 'nht', 'no-resolve-via-default'])
            self.cli_set(base + ['ipv6', 'nht', 'no-resolve-via-default'])

            table = str(int(table) + 1)

        self.cli_commit()

        # Verify route-map properly applied to FRR
        for vrf in vrfs:
            frrconfig = self.getFRRconfig(f'vrf {vrf}', stop_section='^exit-vrf')
            self.assertIn(f'vrf {vrf}', frrconfig)
            self.assertIn(f' no ip nht resolve-via-default', frrconfig)
            self.assertIn(f' no ipv6 nht resolve-via-default', frrconfig)

        # Delete route-maps
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_delete(base + ['ip'])
            self.cli_delete(base + ['ipv6'])

        self.cli_commit()

        # Verify route-map properly is removed from FRR
        for vrf in vrfs:
            frrconfig = self.getFRRconfig(f'vrf {vrf}', stop_section='^exit-vrf')
            self.assertNotIn(f' no ip nht resolve-via-default', frrconfig)
            self.assertNotIn(f' no ipv6 nht resolve-via-default', frrconfig)

    def test_vrf_conntrack(self):
        table = '8710'
        nftables_rules = {
            'vrf_zones_ct_in': ['ct original zone set iifname map @ct_iface_map'],
            'vrf_zones_ct_out': ['ct original zone set oifname map @ct_iface_map']
        }

        self.cli_set(base_path + ['name', 'randomVRF', 'table', '1000'])
        self.cli_commit()

        # Conntrack rules should not be present
        for chain, rule in nftables_rules.items():
            self.verify_nftables_chain(rule, 'inet vrf_zones', chain, inverse=True)

        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.cli_set(base + ['table', table])
            table = str(int(table) + 1)
            # We need the commit inside the loop to trigger the bug in T6603
            self.cli_commit()

        # Every VRF must be present in the conntrack interface map, using its
        # routing table ID as conntrack zone
        zone_map = {tmp['interface'] : tmp['vrf_tableid']
                    for tmp in get_nft_vrf_zone_mapping()}
        self.assertEqual(zone_map['randomVRF'], 1000)
        for index, vrf in enumerate(vrfs):
            self.assertEqual(zone_map[vrf], 8710 + index)

        check_paths = [
            ['nat'],
            ['firewall', 'global-options', 'state-policy', 'established', 'action', 'accept']
        ]

        # conntrack is only enabled once NAT, NAT66 or firewalling is enabled
        for path in check_paths:
            self.cli_set(path)
            self.cli_commit()

            # Conntrack rules should now be present
            for chain, rule in nftables_rules.items():
                self.verify_nftables_chain(rule, 'inet vrf_zones', chain, inverse=False)

            # T6603: there should be only ONE entry for the iifname/oifname in the chains
            tmp = loads(cmdl(['nft', '-j', 'list', 'table', 'inet', 'vrf_zones'], sudo=True))
            num_rules = len(search("nftables[].rule[].chain", tmp))
            # ['vrf_zones_ct_in', 'vrf_zones_ct_out']
            self.assertEqual(num_rules, 2)

            # T6097: the nat anchor the zoning relies on comes and goes with
            # the zone rules - it is not worth its cost when nothing needs it
            self.verify_nftables_chain_exists('inet vrf_zones_nat', 'anchor')

            self.cli_delete([path[0]])
            self.cli_commit()

            for chain, rule in nftables_rules.items():
                self.verify_nftables_chain(rule, 'inet vrf_zones', chain, inverse=True)
            self.verify_nftables_chain_exists('inet vrf_zones_nat', 'anchor',
                                              inverse=True)

    def test_vrf_conntrack_zone_veth(self):
        # T6097: a veth pair connecting two VRFs must pass IPv4 and IPv6
        # traffic while conntrack zoning is active. Both flows have their reply
        # tuple in the default zone 0 (required by T3655), so they collide and
        # only the NAT engine reallocating the clashing tuple keeps the second
        # conntrack entry insertable. That requires a "type nat" chain to be
        # registered - IPv6 used to have none, which is what broke it.
        veth_left = 'veth60'
        veth_right = 'veth61'
        vrf_left = 'ct-left'
        vrf_right = 'ct-right'
        state_policy_path = ['firewall', 'global-options', 'state-policy',
                             'established', 'action', 'accept']

        interfaces = {
            veth_left : {
                'peer' : veth_right,
                'vrf'  : vrf_left,
                'table': '6097',
                'addr' : ['100.64.97.1/30', '2001:db8:6097::1/64'],
            },
            veth_right : {
                'peer' : veth_left,
                'vrf'  : vrf_right,
                'table': '6098',
                'addr' : ['100.64.97.2/30', '2001:db8:6097::2/64'],
            },
        }

        for interface, config in interfaces.items():
            self._cleanup_interfaces.append(interface)
            self.cli_set(base_path + ['name', config['vrf'], 'table', config['table']])
            iface_path = ['interfaces', 'virtual-ethernet', interface]
            self.cli_set(iface_path + ['peer-name', config['peer']])
            self.cli_set(iface_path + ['vrf', config['vrf']])
            for address in config['addr']:
                self.cli_set(iface_path + ['address', address])

        # Conntrack zoning is only installed once conntrack is actually
        # required - a stateful firewall rule is enough to trigger it
        self.cli_set(state_policy_path)
        self._cleanup_paths.append(['firewall', 'global-options', 'state-policy'])
        self.cli_commit()

        # The reply tuple collision is only resolved while the nat anchor is
        # there. Check it explicitly so a missing anchor is not mistaken for a
        # conntrack zoning regression.
        self.verify_nftables_chain_exists('inet vrf_zones_nat', 'anchor')

        # Both the VRF devices and their member interfaces must be zoned
        zone_map = {tmp['interface'] : tmp['vrf_tableid']
                    for tmp in get_nft_vrf_zone_mapping()}
        for interface, config in interfaces.items():
            self.assertEqual(zone_map[interface], int(config['table']))
            self.assertEqual(zone_map[config['vrf']], int(config['table']))

        # Wait for IPv6 duplicate address detection to finish, otherwise the
        # source address can not be used yet
        for interface in interfaces:
            self.assertTrue(wait_for(dad_completed, interface, timeout=10))

        insert_failed = get_conntrack_insert_failed()
        for destination in ['100.64.97.2', '2001:db8:6097::2']:
            ping_in_vrf(vrf_left, destination, f'ping {destination} failed')

        # No conntrack entry may have been rejected while doing so
        self.assertEqual(insert_failed, get_conntrack_insert_failed())

    def test_vrf_conntrack_route_leak(self):
        # T3655: the default route is leaked from the default VRF into VRF red
        # and blue and the traffic is NATed in the default VRF. The reply comes
        # back in on the uplink, which carries no conntrack zone at all, so it
        # can only be matched because the reply tuple was left in zone 0 - and
        # it has to end up in the VRF the flow originated from.
        #
        # The peer of the uplink is put into a network namespace so it behaves
        # like the remote host it stands in for. Terminating it on this box
        # instead would track the very same flow a second time and produce a
        # conntrack collision that does not exist in the topology under test.
        netns = 'leakisp'
        uplink = 'veth66'
        server = 'veth67'
        uplink_addr4 = '203.0.113.1/29'
        uplink_addr6 = '2001:db8:113::1/64'
        server_addr4 = '203.0.113.2/29'
        server_addr6 = '2001:db8:113::2/64'
        lans = {
            'leakred'  : {'table' : '6099', 'gw_if' : 'veth62', 'cl_if' : 'veth63',
                          'cl_vrf': 'leakcla', 'cl_table' : '6101',
                          'gw4' : '192.0.2.1/29',  'cl4' : '192.0.2.2/29',
                          'gw6' : '2001:db8:2::1/64', 'cl6' : '2001:db8:2::2/64',
                          'net4': '192.0.2.0/29', 'net6' : '2001:db8:2::/64'},
            'leakblue' : {'table' : '6100', 'gw_if' : 'veth64', 'cl_if' : 'veth65',
                          'cl_vrf': 'leakclb', 'cl_table' : '6102',
                          'gw4' : '192.0.2.9/29',  'cl4' : '192.0.2.10/29',
                          'gw6' : '2001:db8:3::1/64', 'cl6' : '2001:db8:3::2/64',
                          'net4': '192.0.2.8/29', 'net6' : '2001:db8:3::/64'},
        }
        interfaces = [uplink, server]

        def veth(name, peer, addresses=None, vrf=None):
            self._cleanup_interfaces.append(name)
            path = ['interfaces', 'virtual-ethernet', name]
            self.cli_set(path + ['peer-name', peer])
            if vrf:
                self.cli_set(path + ['vrf', vrf])
            for address in addresses or []:
                self.cli_set(path + ['address', address])

        # The uplink is the "pppoe0" of T3655 and lives in the default VRF
        veth(uplink, server, [uplink_addr4, uplink_addr6])
        veth(server, uplink)

        for gw_vrf, config in lans.items():
            interfaces += [config['gw_if'], config['cl_if']]
            self.cli_set(base_path + ['name', gw_vrf, 'table', config['table']])
            self.cli_set(base_path + ['name', config['cl_vrf'], 'table',
                                      config['cl_table']])
            veth(config['gw_if'], config['cl_if'],
                 [config['gw4'], config['gw6']], vrf=gw_vrf)
            veth(config['cl_if'], config['gw_if'],
                 [config['cl4'], config['cl6']], vrf=config['cl_vrf'])

            # Leak the default route out of the VRF into the default VRF ...
            gw_static = base_path + ['name', gw_vrf, 'protocols', 'static']
            self.cli_set(gw_static + ['route', '0.0.0.0/0', 'interface', uplink,
                                      'vrf', 'default'])
            self.cli_set(gw_static + ['route6', '::/0', 'interface', uplink,
                                      'vrf', 'default'])
            # ... and leak the LAN prefixes back, so the reply can be routed
            # into the VRF it belongs to once conntrack un-NATed it
            self.cli_set(['protocols', 'static', 'route', config['net4'],
                          'interface', config['gw_if'], 'vrf', gw_vrf])
            self.cli_set(['protocols', 'static', 'route6', config['net6'],
                          'interface', config['gw_if'], 'vrf', gw_vrf])
            self._cleanup_paths.append(['protocols', 'static', 'route',
                                        config['net4']])
            self._cleanup_paths.append(['protocols', 'static', 'route6',
                                        config['net6']])
            # Client default route points at its gateway
            cl_static = base_path + ['name', config['cl_vrf'], 'protocols',
                                     'static']
            self.cli_set(cl_static + ['route', '0.0.0.0/0', 'next-hop',
                                      config['gw4'].split('/')[0]])
            self.cli_set(cl_static + ['route6', '::/0', 'next-hop',
                                      config['gw6'].split('/')[0]])

        # NAT happens in the default VRF, on the uplink. This also enables the
        # conntrack zoning, conntrack_required() lists 'nat'
        self.cli_set(['nat', 'source', 'rule', '100', 'outbound-interface',
                      'name', uplink])
        self.cli_set(['nat', 'source', 'rule', '100', 'translation', 'address',
                      'masquerade'])
        self._cleanup_paths.append(['nat', 'source', 'rule', '100'])
        self.cli_commit()

        # The far end stands in for a remote host, so it has to live in its own
        # network namespace - terminating the flow on this box would track it a
        # second time and produce a conntrack collision the real topology does
        # not have. VyOS can not build a veth pair straddling a namespace
        # (it would create one pair on each side), so move the peer over here.
        self._cleanup_netns.append((netns, server))
        cmdl(['ip', 'netns', 'add', netns], sudo=True)
        cmdl(['ip', 'link', 'set', server, 'netns', netns], sudo=True)
        in_netns = ['ip', 'netns', 'exec', netns]
        cmdl(in_netns + ['ip', 'link', 'set', server, 'up'], sudo=True)
        cmdl(in_netns + ['ip', 'addr', 'add', server_addr4, 'dev', server],
             sudo=True)
        cmdl(in_netns + ['ip', 'addr', 'add', server_addr6, 'dev', server,
                         'nodad'], sudo=True)
        # IPv6 is not NATed, so the far end needs a route back per LAN
        for config in lans.values():
            cmdl(in_netns + ['ip', '-6', 'route', 'add', config['net6'], 'via',
                             uplink_addr6.split('/')[0]], sudo=True)

        for interface in interfaces:
            if interface == server:
                continue
            self.assertTrue(wait_for(dad_completed, interface, timeout=10))

        insert_failed = get_conntrack_insert_failed()
        for gw_vrf, config in lans.items():
            for destination in [server_addr4.split('/')[0],
                                server_addr6.split('/')[0]]:
                ping_in_vrf(config['cl_vrf'], destination,
                            f'{config["cl_vrf"]} -> {destination} failed, '
                            f'leaked via {gw_vrf}')

            # The flow is tracked in the zone of the VRF it entered, and it must
            # have seen a reply - an unmatched reply shows up as [UNREPLIED]
            zone = f'zone-orig={config["table"]}'
            conntrack = get_conntrack_entries()
            self.assertIn(zone, conntrack)
            for line in conntrack.splitlines():
                if zone in line:
                    self.assertNotIn('[UNREPLIED]', line)

        # Leaking must not cost us a single conntrack entry
        self.assertEqual(insert_failed, get_conntrack_insert_failed())

    def test_vrf_policy_based_route(self):
        vrf_name = 'test-pbr_123'

        self.cli_set(base_path + ['name', vrf_name, 'table', '17563'])

        policy_path = ['policy', 'route', 'pbr_smoke4', 'rule', '10']
        self.cli_set(policy_path + ['action', 'accept'])
        self.cli_set(policy_path + ['set', 'vrf', vrf_name])
        self.cli_set(policy_path + ['source', 'address', '192.0.2.1/32'])

        policy6_path = ['policy', 'route6', 'pbr_smoke6', 'rule', '10']
        self.cli_set(policy6_path + ['action', 'accept'])
        self.cli_set(policy6_path + ['set', 'vrf', vrf_name])
        self.cli_set(policy6_path + ['source', 'address', '2001:db8::/56'])

        local_policy_path = ['policy', 'local-route', 'rule', '10']
        self.cli_set(local_policy_path + ['set', 'vrf', vrf_name])
        self.cli_set(local_policy_path + ['source', 'address', '192.0.2.1/32'])

        local_policy6_path = ['policy', 'local-route6', 'rule', '10']
        self.cli_set(local_policy6_path + ['set', 'vrf', vrf_name])
        self.cli_set(local_policy6_path + ['source', 'address', '2001:db8::/56'])

        self.cli_commit()

        self.cli_delete(base_path)
        # check validate() - VRF referenced in policy based routing
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(['policy', 'route'])
        # check validate() - VRF referenced in policy based routing
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(['policy', 'route6'])
        # check validate() - VRF referenced in policy based routing
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(['policy', 'local-route'])
        # check validate() - VRF referenced in policy based routing
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(['policy', 'local-route6'])

        self.cli_commit()

    def test_dhcp_single_pool(self):
        # Prepare the vrf and options
        table = '100'
        vrf = 'dhcp_smoke'
        interface = 'dum8888'
        subnet = '192.0.2.0/25'
        router = inc_ip(subnet, 1)
        dns_1 = inc_ip(subnet, 2)
        dns_2 = inc_ip(subnet, 3)
        domain_name = 'vyos.net'

        # declare files
        process_name = 'kea-dhcp4'
        kea4_conf = f'/var/run/kea/kea-{vrf}-dhcp4.conf'

        # create interface
        cidr_mask = subnet.split('/')[-1]
        self.cli_set(
            ['interfaces', 'dummy', interface, 'address', f'{router}/{cidr_mask}']
        )
        self.cli_set(['interfaces', 'dummy', interface, 'vrf', f'{vrf}'])

        # create the vrf with table
        base = base_path + ['name', vrf]
        self.cli_set(base + ['table', table])

        # set the dhcp scope
        base = base_path + ['name', vrf, 'service', 'dhcp-server']
        shared_net_name = 'SMOKE-1'

        range_0_start = inc_ip(subnet, 10)
        range_0_stop = inc_ip(subnet, 20)
        range_1_start = inc_ip(subnet, 40)
        range_1_stop = inc_ip(subnet, 50)

        self.cli_set(base + ['listen-interface', interface])

        self.cli_set(base + ['shared-network-name', shared_net_name, 'ping-check'])

        pool = base + ['shared-network-name', shared_net_name, 'subnet', subnet]
        self.cli_set(pool + ['subnet-id', '1'])
        self.cli_set(pool + ['ignore-client-id'])
        self.cli_set(pool + ['ping-check'])
        # we use the first subnet IP address as default gateway
        self.cli_set(pool + ['option', 'default-router', router])
        self.cli_set(pool + ['option', 'name-server', dns_1])
        self.cli_set(pool + ['option', 'name-server', dns_2])
        self.cli_set(pool + ['option', 'domain-name', domain_name])

        # check validate() - No DHCP address range or active static-mapping set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(pool + ['range', '0', 'start', range_0_start])
        self.cli_set(pool + ['range', '0', 'stop', range_0_stop])
        self.cli_set(pool + ['range', '1', 'start', range_1_start])
        self.cli_set(pool + ['range', '1', 'stop', range_1_stop])

        # commit changes
        self.cli_commit()

        config = read_file(kea4_conf)
        obj = loads(config)

        self.verify_config_value(
            obj, ['Dhcp4', 'interfaces-config'], 'interfaces', [interface]
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks'], 'name', shared_net_name
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'id', 1
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'match-client-id', False
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'valid-lifetime', 86400
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'max-valid-lifetime', 86400
        )

        # Verify ping-check
        self.verify_config_value(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'user-context'],
            'enable-ping-check',
            True,
        )

        self.verify_config_value(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'user-context'],
            'enable-ping-check',
            True,
        )

        # Verify options
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'domain-name', 'data': domain_name},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'domain-name-servers', 'data': f'{dns_1}, {dns_2}'},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'routers', 'data': router},
        )

        # Verify pools
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
            {'pool': f'{range_0_start} - {range_0_stop}'},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
            {'pool': f'{range_1_start} - {range_1_stop}'},
        )

        # Check for running process
        self.verify_kea_service_running(process_name)

        # perform cleanup
        self.cli_delete(['interfaces', 'dummy', interface, 'address'])
        self.cli_delete(['interfaces', 'dummy', interface, 'vrf'])
        self.cli_delete(base)
        self.cli_commit()

    def test_dhcp_vrf_default_route(self):
        # T7927 - when retrieving a default route via DHCP, check that additional
        # calls into FRRender() keep the DHCP route in place
        vrf_name = 'red-16'
        default_gateway = '192.0.2.1'
        dhcp_if_server = 'veth0'
        dhcp_if_client = 'veth1'

        default_distance = default_value(['interfaces', 'virtual-ethernet',
                                          dhcp_if_client, 'dhcp-options',
                                          'default-route-distance'])

        dhcp_pool_base = ['service', 'dhcp-server', 'shared-network-name',
                          'FOO-4', 'subnet', '192.0.2.0/24']
        veth_base = ['interfaces', 'virtual-ethernet']

        # Start DHCP Server in VRF connected via veth pair to default VRF
        self.cli_set(['vrf', 'name', vrf_name, 'table', '48752'])
        self.cli_set(veth_base + [dhcp_if_server, 'address', '192.0.2.1/24'])
        self.cli_set(veth_base + [dhcp_if_server, 'peer-name', dhcp_if_client])
        self.cli_set(veth_base + [dhcp_if_client, 'peer-name', dhcp_if_server])
        self.cli_set(veth_base + [dhcp_if_client, 'vrf', vrf_name])

        self.cli_set(['service', 'dhcp-server', 'listen-interface', dhcp_if_server])
        self.cli_set(dhcp_pool_base + ['option', 'default-router', default_gateway])
        self.cli_set(dhcp_pool_base + ['range', 'uno', 'start', '192.0.2.10'])
        self.cli_set(dhcp_pool_base + ['range', 'uno', 'stop', '192.0.2.30'])
        self.cli_set(dhcp_pool_base + ['subnet-id', '1'])

        self.cli_commit()

        # Start DHCP client in VRF
        self.cli_set(['interfaces', 'virtual-ethernet', dhcp_if_client, 'address', 'dhcp'])
        self.cli_commit()

        # define helper for the string we are looking for in FRR configuration
        # the leading whitespace is required as this lives under a VRF context!
        test_ok_string = f' ip route 0.0.0.0/0 {default_gateway} {dhcp_if_client}'\
                         f' tag 210 {default_distance}'

        def test_callback(self, vrf_name, string) -> bool:
            tmp = self.getFRRconfig(f'^vrf {vrf_name}', stop_section='^exit-vrf')
            return bool(string in tmp)

        # We need to wait until DHCP client has started and an IP address has been received
        tmp = wait_for(test_callback, self, vrf_name, test_ok_string, timeout=20.0)
        self.assertTrue(tmp)

        # Change anything in FRR to re-trigger config generation. DHCP route
        # must still be present
        self.cli_set(['protocols', 'static', 'route', '10.0.0.0/24', 'blackhole'])
        self.cli_commit()

        frrconfig = self.getFRRconfig(f'^vrf {vrf_name}', stop_section='^exit-vrf')
        self.assertIn(test_ok_string, frrconfig)

        self.cli_delete(['interfaces', 'virtual-ethernet'])
        self.cli_delete(['service', 'dhcp-server'])

    def test_dhcpv6_single_pool(self):
        # Prepare the vrf and other options
        table = '100'
        vrf = 'dhcp_smoke'
        subnet = '2001:db8:f00::/64'
        dns_1 = '2001:db8::1'
        dns_2 = '2001:db8::2'
        domain = 'vyos.net'
        nis_servers = ['2001:db8:ffff::1', '2001:db8:ffff::2']
        interface = 'dum8888'
        interface_addr = inc_ip(subnet, 1) + '/64'

        # declare files
        process_name = 'kea-dhcp6'
        kea6_conf = f'/var/run/kea/kea-{vrf}-dhcp6.conf'

        # create interface
        self.cli_set(['interfaces', 'dummy', interface, 'address', f'{interface_addr}'])
        self.cli_set(['interfaces', 'dummy', interface, 'vrf', f'{vrf}'])

        # create the vrf with table
        base = base_path + ['name', vrf]
        self.cli_set(base + ['table', table])

        # set the dhcp scope
        base = base_path + ['name', vrf, 'service', 'dhcpv6-server']

        shared_net_name = 'SMOKE-1'
        search_domains = ['foo.vyos.net', 'bar.vyos.net']
        lease_time = '1200'
        max_lease_time = '72000'
        min_lease_time = '600'
        preference = '10'
        sip_server = 'sip.vyos.net'
        sntp_server = inc_ip(subnet, 100)
        range_start = inc_ip(subnet, 256)  # ::100
        range_stop = inc_ip(subnet, 65535)  # ::ffff

        pool = base + ['shared-network-name', shared_net_name, 'subnet', subnet]

        self.cli_set(base + ['preference', preference])
        self.cli_set(pool + ['interface', interface])
        self.cli_set(pool + ['subnet-id', '1'])
        # we use the first subnet IP address as default gateway
        self.cli_set(pool + ['lease-time', 'default', lease_time])
        self.cli_set(pool + ['lease-time', 'maximum', max_lease_time])
        self.cli_set(pool + ['lease-time', 'minimum', min_lease_time])
        self.cli_set(pool + ['option', 'capwap-controller', dns_1])
        self.cli_set(pool + ['option', 'name-server', dns_1])
        self.cli_set(pool + ['option', 'name-server', dns_2])
        self.cli_set(pool + ['option', 'name-server', dns_2])
        self.cli_set(pool + ['option', 'nis-domain', domain])
        self.cli_set(pool + ['option', 'nisplus-domain', domain])
        self.cli_set(pool + ['option', 'sip-server', sip_server])
        self.cli_set(pool + ['option', 'sntp-server', sntp_server])
        self.cli_set(pool + ['range', '1', 'start', range_start])
        self.cli_set(pool + ['range', '1', 'stop', range_stop])

        for server in nis_servers:
            self.cli_set(pool + ['option', 'nis-server', server])
            self.cli_set(pool + ['option', 'nisplus-server', server])

        for search_domain in search_domains:
            self.cli_set(pool + ['option', 'domain-search', search_domain])

        client_base = 1
        for client in ['client1', 'client2', 'client3']:
            duid = f'00:01:00:01:12:34:56:78:aa:bb:cc:dd:ee:{client_base:02}'
            self.cli_set(pool + ['static-mapping', client, 'duid', duid])
            self.cli_set(
                pool
                + [
                    'static-mapping',
                    client,
                    'ipv6-address',
                    inc_ip(subnet, client_base),
                ]
            )
            self.cli_set(
                pool
                + [
                    'static-mapping',
                    client,
                    'ipv6-prefix',
                    inc_ip(subnet, client_base << 64) + '/64',
                ]
            )
            client_base += 1

        # cannot have both mac-address and duid set
        with self.assertRaises(ConfigSessionError):
            self.cli_set(
                pool + ['static-mapping', 'client1', 'mac', '00:50:00:00:00:11']
            )
            self.cli_commit()
        self.cli_delete(pool + ['static-mapping', 'client1', 'mac'])

        # commit changes
        self.cli_commit()

        config = read_file(kea6_conf)
        obj = loads(config)

        self.verify_config_value(
            obj, ['Dhcp6', 'shared-networks'], 'name', shared_net_name
        )
        self.verify_config_value(
            obj, ['Dhcp6', 'shared-networks', 0, 'subnet6'], 'subnet', subnet
        )
        self.verify_config_value(
            obj, ['Dhcp6', 'shared-networks', 0, 'subnet6'], 'interface', interface
        )
        self.verify_config_value(
            obj, ['Dhcp6', 'shared-networks', 0, 'subnet6'], 'id', 1
        )
        self.verify_config_value(
            obj,
            ['Dhcp6', 'shared-networks', 0, 'subnet6'],
            'valid-lifetime',
            int(lease_time),
        )
        self.verify_config_value(
            obj,
            ['Dhcp6', 'shared-networks', 0, 'subnet6'],
            'min-valid-lifetime',
            int(min_lease_time),
        )
        self.verify_config_value(
            obj,
            ['Dhcp6', 'shared-networks', 0, 'subnet6'],
            'max-valid-lifetime',
            int(max_lease_time),
        )

        # Verify options
        self.verify_config_object(
            obj,
            ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
            {'name': 'capwap-ac-v6', 'data': dns_1},
        )
        self.verify_config_object(
            obj,
            ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
            {'name': 'dns-servers', 'data': f'{dns_1}, {dns_2}'},
        )
        self.verify_config_object(
            obj,
            ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
            {'name': 'domain-search', 'data': ', '.join(search_domains)},
        )
        self.verify_config_object(
            obj,
            ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
            {'name': 'nis-domain-name', 'data': domain},
        )
        self.verify_config_object(
            obj,
            ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
            {'name': 'nis-servers', 'data': ', '.join(nis_servers)},
        )
        self.verify_config_object(
            obj,
            ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
            {'name': 'nisp-domain-name', 'data': domain},
        )
        self.verify_config_object(
            obj,
            ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
            {'name': 'nisp-servers', 'data': ', '.join(nis_servers)},
        )
        self.verify_config_object(
            obj,
            ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
            {'name': 'sntp-servers', 'data': sntp_server},
        )
        self.verify_config_object(
            obj,
            ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
            {'name': 'sip-server-dns', 'data': sip_server},
        )

        # Verify pools
        self.verify_config_object(
            obj,
            ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'pools'],
            {'pool': f'{range_start} - {range_stop}'},
        )

        client_base = 1
        for client in ['client1', 'client2', 'client3']:
            duid = f'00:01:00:01:12:34:56:78:aa:bb:cc:dd:ee:{client_base:02}'
            ip = inc_ip(subnet, client_base)
            prefix = inc_ip(subnet, client_base << 64) + '/64'

            self.verify_config_object(
                obj,
                ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'reservations'],
                {
                    'hostname': client,
                    'duid': duid,
                    'ip-addresses': [ip],
                    'prefixes': [prefix],
                },
            )

            client_base += 1

        # Check for running process
        self.verify_kea_service_running(process_name)

        # perform cleanup
        self.cli_delete(['interfaces', 'dummy', interface, 'address'])
        self.cli_delete(['interfaces', 'dummy', interface, 'vrf'])
        self.cli_delete(base)
        self.cli_commit()


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
