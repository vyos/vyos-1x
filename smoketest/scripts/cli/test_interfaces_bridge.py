#!/usr/bin/env python3
#
# Copyright (C) 2020-2022 VyOS maintainers and contributors
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
import json
import unittest

from base_interfaces_test import BasicInterfaceTest
from copy import deepcopy
from glob import glob
from netifaces import interfaces

from vyos.ifconfig import Section
from vyos.util import cmd
from vyos.util import read_file
from vyos.util import get_interface_config
from vyos.validate import is_intf_addr_assigned

class BridgeInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._test_dhcp = True
        cls._test_ip = True
        cls._test_ipv6 = True
        cls._test_ipv6_pd = True
        cls._test_ipv6_dhcpc6 = True
        cls._test_vlan = True
        cls._base_path = ['interfaces', 'bridge']
        cls._mirror_interfaces = ['dum21354']
        cls._members = []

        # we need to filter out VLAN interfaces identified by a dot (.)
        # in their name - just in case!
        if 'TEST_ETH' in os.environ:
            cls._members = os.environ['TEST_ETH'].split()
        else:
            for tmp in Section.interfaces('ethernet'):
                if not '.' in tmp:
                    cls._members.append(tmp)

        cls._options['br0'] = []
        for member in cls._members:
            cls._options['br0'].append(f'member interface {member}')
        cls._interfaces = list(cls._options)

        # call base-classes classmethod
        super(BridgeInterfaceTest, cls).setUpClass()

    def tearDown(self):
        for intf in self._interfaces:
            self.cli_delete(self._base_path + [intf])

        super().tearDown()

    def test_isolated_interfaces(self):
        # Add member interfaces to bridge and set STP cost/priority
        for interface in self._interfaces:
            base = self._base_path + [interface]
            self.cli_set(base + ['stp'])

            # assign members to bridge interface
            for member in self._members:
                base_member = base + ['member', 'interface', member]
                self.cli_set(base_member + ['isolated'])

        # commit config
        self.cli_commit()

        for interface in self._interfaces:
            tmp = get_interface_config(interface)
            # STP must be enabled as configured above
            self.assertEqual(1, tmp['linkinfo']['info_data']['stp_state'])

            # validate member interface configuration
            for member in self._members:
                tmp = get_interface_config(member)
                # verify member is assigned to the bridge
                self.assertEqual(interface, tmp['master'])
                # Isolated must be enabled as configured above
                self.assertTrue(tmp['linkinfo']['info_slave_data']['isolated'])

    def test_igmp_querier_snooping(self):
        # Add member interfaces to bridge
        for interface in self._interfaces:
            base = self._base_path + [interface]

            # assign members to bridge interface
            for member in self._members:
                base_member = base + ['member', 'interface', member]
                self.cli_set(base_member)

        # commit config
        self.cli_commit()

        for interface in self._interfaces:
            # Verify IGMP default configuration
            tmp = read_file(f'/sys/class/net/{interface}/bridge/multicast_snooping')
            self.assertEqual(tmp, '0')
            tmp = read_file(f'/sys/class/net/{interface}/bridge/multicast_querier')
            self.assertEqual(tmp, '0')

        # Enable IGMP snooping
        for interface in self._interfaces:
            base = self._base_path + [interface]
            self.cli_set(base + ['igmp', 'snooping'])

        # commit config
        self.cli_commit()

        for interface in self._interfaces:
            # Verify IGMP snooping configuration
            # Verify IGMP default configuration
            tmp = read_file(f'/sys/class/net/{interface}/bridge/multicast_snooping')
            self.assertEqual(tmp, '1')
            tmp = read_file(f'/sys/class/net/{interface}/bridge/multicast_querier')
            self.assertEqual(tmp, '0')

        # Enable IGMP querieer
        for interface in self._interfaces:
            base = self._base_path + [interface]
            self.cli_set(base + ['igmp', 'querier'])

        # commit config
        self.cli_commit()

        for interface in self._interfaces:
            # Verify IGMP snooping & querier configuration
            tmp = read_file(f'/sys/class/net/{interface}/bridge/multicast_snooping')
            self.assertEqual(tmp, '1')
            tmp = read_file(f'/sys/class/net/{interface}/bridge/multicast_querier')
            self.assertEqual(tmp, '1')

        # Disable IGMP
        for interface in self._interfaces:
            base = self._base_path + [interface]
            self.cli_delete(base + ['igmp'])

        # commit config
        self.cli_commit()

        for interface in self._interfaces:
            # Verify IGMP snooping & querier configuration
            tmp = read_file(f'/sys/class/net/{interface}/bridge/multicast_snooping')
            self.assertEqual(tmp, '0')
            tmp = read_file(f'/sys/class/net/{interface}/bridge/multicast_querier')
            self.assertEqual(tmp, '0')

            # validate member interface configuration
            for member in self._members:
                tmp = get_interface_config(member)
                # verify member is assigned to the bridge
                self.assertEqual(interface, tmp['master'])


    def test_add_remove_bridge_member(self):
        # Add member interfaces to bridge and set STP cost/priority
        for interface in self._interfaces:
            base = self._base_path + [interface]
            self.cli_set(base + ['stp'])
            self.cli_set(base + ['address', '192.0.2.1/24'])

            cost = 1000
            priority = 10
            # assign members to bridge interface
            for member in self._members:
                base_member = base + ['member', 'interface', member]
                self.cli_set(base_member + ['cost', str(cost)])
                self.cli_set(base_member + ['priority', str(priority)])
                cost += 1
                priority += 1

        # commit config
        self.cli_commit()

        # Add member interfaces to bridge and set STP cost/priority
        for interface in self._interfaces:
            cost = 1000
            priority = 10
            for member in self._members:
                tmp = get_interface_config(member)
                self.assertEqual(interface, tmp['master'])
                self.assertFalse(           tmp['linkinfo']['info_slave_data']['isolated'])
                self.assertEqual(cost,      tmp['linkinfo']['info_slave_data']['cost'])
                self.assertEqual(priority,  tmp['linkinfo']['info_slave_data']['priority'])

                cost += 1
                priority += 1


    def test_vif_8021q_interfaces(self):
        for interface in self._interfaces:
            base = self._base_path + [interface]
            self.cli_set(base + ['enable-vlan'])
        super().test_vif_8021q_interfaces()

    def test_vif_8021q_lower_up_down(self):
        for interface in self._interfaces:
            base = self._base_path + [interface]
            self.cli_set(base + ['enable-vlan'])
        super().test_vif_8021q_lower_up_down()

    def test_vif_8021q_qos_change(self):
        for interface in self._interfaces:
            base = self._base_path + [interface]
            self.cli_set(base + ['enable-vlan'])
        super().test_vif_8021q_qos_change()

    def test_vif_8021q_mtu_limits(self):
        for interface in self._interfaces:
            base = self._base_path + [interface]
            self.cli_set(base + ['enable-vlan'])
        super().test_vif_8021q_mtu_limits()

    def test_bridge_vlan_filter(self):
        vifs = ['10', '20', '30', '40']
        native_vlan = '20'

        # Add member interface to bridge and set VLAN filter
        for interface in self._interfaces:
            base = self._base_path + [interface]
            self.cli_set(base + ['enable-vlan'])
            self.cli_set(base + ['address', '192.0.2.1/24'])

            for vif in vifs:
                self.cli_set(base + ['vif', vif, 'address', f'192.0.{vif}.1/24'])
                self.cli_set(base + ['vif', vif, 'mtu', self._mtu])

            for member in self._members:
                base_member = base + ['member', 'interface', member]
                self.cli_set(base_member + ['native-vlan', native_vlan])
                for vif in vifs:
                    self.cli_set(base_member + ['allowed-vlan', vif])

        # commit config
        self.cli_commit()

        def _verify_members(interface, members) -> None:
            # check member interfaces are added on the bridge
            bridge_members = []
            for tmp in glob(f'/sys/class/net/{interface}/lower_*'):
                bridge_members.append(os.path.basename(tmp).replace('lower_', ''))

            self.assertListEqual(sorted(members), sorted(bridge_members))

        def _check_vlan_filter(interface, vifs) -> None:
            configured_vlan_ids = []

            bridge_json = cmd(f'bridge -j vlan show dev {interface}')
            bridge_json = json.loads(bridge_json)
            self.assertIsNotNone(bridge_json)

            for tmp in bridge_json:
                self.assertIn('vlans', tmp)

                for vlan in tmp['vlans']:
                    self.assertIn('vlan', vlan)
                    configured_vlan_ids.append(str(vlan['vlan']))

                    # Verify native VLAN ID has 'PVID' flag set on individual member ports
                    if not interface.startswith('br') and str(vlan['vlan']) == native_vlan:
                        self.assertIn('flags', vlan)
                        self.assertIn('PVID', vlan['flags'])

            self.assertListEqual(sorted(configured_vlan_ids), sorted(vifs))

        # Verify correct setting of VLAN filter function
        for interface in self._interfaces:
            tmp = read_file(f'/sys/class/net/{interface}/bridge/vlan_filtering')
            self.assertEqual(tmp, '1')

        # Obtain status information and verify proper VLAN filter setup.
        # First check if all members are present, second check if all VLANs
        # are assigned on the parend bridge interface, third verify all the
        # VLANs are properly setup on the downstream "member" ports
        for interface in self._interfaces:
            # check member interfaces are added on the bridge
            _verify_members(interface, self._members)

            # Check if all VLAN ids are properly set up. Bridge interface always
            # has native VLAN 1
            tmp = deepcopy(vifs)
            tmp.append('1')
            _check_vlan_filter(interface, tmp)

            for member in self._members:
                _check_vlan_filter(member, vifs)

        # change member interface description to trigger config update,
        # VLANs must still exist (T4565)
        for interface in self._interfaces:
            for member in self._members:
                self.cli_set(['interfaces', Section.section(member), member, 'description', f'foo {member}'])

        # commit config
        self.cli_commit()

        # Obtain status information and verify proper VLAN filter setup.
        # First check if all members are present, second check if all VLANs
        # are assigned on the parend bridge interface, third verify all the
        # VLANs are properly setup on the downstream "member" ports
        for interface in self._interfaces:
            # check member interfaces are added on the bridge
            _verify_members(interface, self._members)

            # Check if all VLAN ids are properly set up. Bridge interface always
            # has native VLAN 1
            tmp = deepcopy(vifs)
            tmp.append('1')
            _check_vlan_filter(interface, tmp)

            for member in self._members:
                _check_vlan_filter(member, vifs)

        # delete all members
        for interface in self._interfaces:
            self.cli_delete(self._base_path + [interface, 'member'])

        # commit config
        self.cli_commit()

        # verify member interfaces are no longer assigned on the bridge
        for interface in self._interfaces:
            bridge_members = []
            for tmp in glob(f'/sys/class/net/{interface}/lower_*'):
                bridge_members.append(os.path.basename(tmp).replace('lower_', ''))

            self.assertNotEqual(len(self._members), len(bridge_members))
            for member in self._members:
                self.assertNotIn(member, bridge_members)

    def test_bridge_vif_members(self):
        # T2945: ensure that VIFs are not dropped from bridge
        vifs = ['300', '400']
        for interface in self._interfaces:
            for member in self._members:
                for vif in vifs:
                    self.cli_set(['interfaces', 'ethernet', member, 'vif', vif])
                    self.cli_set(['interfaces', 'bridge', interface, 'member', 'interface', f'{member}.{vif}'])

        self.cli_commit()

        # Verify config
        for interface in self._interfaces:
            for member in self._members:
                for vif in vifs:
                    # member interface must be assigned to the bridge
                    self.assertTrue(os.path.exists(f'/sys/class/net/{interface}/lower_{member}.{vif}'))

        # delete all members
        for interface in self._interfaces:
            for member in self._members:
                for vif in vifs:
                    self.cli_delete(['interfaces', 'ethernet', member, 'vif', vif])
                    self.cli_delete(['interfaces', 'bridge', interface, 'member', 'interface', f'{member}.{vif}'])

    def test_bridge_vif_s_vif_c_members(self):
        # T2945: ensure that VIFs are not dropped from bridge
        vifs = ['300', '400']
        vifc = ['301', '401']
        for interface in self._interfaces:
            for member in self._members:
                for vif_s in vifs:
                    for vif_c in vifc:
                        self.cli_set(['interfaces', 'ethernet', member, 'vif-s', vif_s, 'vif-c', vif_c])
                        self.cli_set(['interfaces', 'bridge', interface, 'member', 'interface', f'{member}.{vif_s}.{vif_c}'])

        self.cli_commit()

        # Verify config
        for interface in self._interfaces:
            for member in self._members:
                for vif_s in vifs:
                    for vif_c in vifc:
                        # member interface must be assigned to the bridge
                        self.assertTrue(os.path.exists(f'/sys/class/net/{interface}/lower_{member}.{vif_s}.{vif_c}'))

        # delete all members
        for interface in self._interfaces:
            for member in self._members:
                for vif_s in vifs:
                    self.cli_delete(['interfaces', 'ethernet', member, 'vif-s', vif_s])
                    for vif_c in vifc:
                        self.cli_delete(['interfaces', 'bridge', interface, 'member', 'interface', f'{member}.{vif_s}.{vif_c}'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
