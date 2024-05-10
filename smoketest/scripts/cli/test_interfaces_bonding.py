#!/usr/bin/env python3
#
# Copyright (C) 2020-2023 VyOS maintainers and contributors
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

from base_interfaces_test import BasicInterfaceTest

from vyos.ifconfig import Section
from vyos.ifconfig.interface import Interface
from vyos.configsession import ConfigSessionError
from vyos.utils.network import get_interface_config
from vyos.utils.file import read_file

class BondingInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'bonding']
        cls._mirror_interfaces = ['dum21354']
        cls._members = []

        # we need to filter out VLAN interfaces identified by a dot (.)
        # in their name - just in case!
        if 'TEST_ETH' in os.environ:
            cls._members = os.environ['TEST_ETH'].split()
        else:
            for tmp in Section.interfaces('ethernet', vlan=False):
                cls._members.append(tmp)

        cls._options = {'bond0' : []}
        for member in cls._members:
            cls._options['bond0'].append(f'member interface {member}')
        cls._interfaces = list(cls._options)

        # call base-classes classmethod
        super(BondingInterfaceTest, cls).setUpClass()

    def test_add_single_ip_address(self):
        super().test_add_single_ip_address()

        for interface in self._interfaces:
            slaves = read_file(f'/sys/class/net/{interface}/bonding/slaves').split()
            self.assertListEqual(slaves, self._members)

    def test_vif_8021q_interfaces(self):
        super().test_vif_8021q_interfaces()

        for interface in self._interfaces:
            slaves = read_file(f'/sys/class/net/{interface}/bonding/slaves').split()
            self.assertListEqual(slaves, self._members)

    def test_bonding_remove_member(self):
        # T2515: when removing a bond member the previously enslaved/member
        # interface must be in its former admin-up/down state. Here we ensure
        # that it is admin-up as it was admin-up before.

        # configure member interfaces
        for interface in self._interfaces:
            for option in self._options.get(interface, []):
                self.cli_set(self._base_path + [interface] + option.split())

        self.cli_commit()

        # remove single bond member port
        for interface in self._interfaces:
            remove_member = self._members[0]
            self.cli_delete(self._base_path + [interface, 'member', 'interface', remove_member])

        self.cli_commit()

        # removed member port must be admin-up
        for interface in self._interfaces:
            remove_member = self._members[0]
            state = Interface(remove_member).get_admin_state()
            self.assertEqual('up', state)

    def test_bonding_min_links(self):
        # configure member interfaces
        min_links = len(self._interfaces)
        for interface in self._interfaces:
            for option in self._options.get(interface, []):
                self.cli_set(self._base_path + [interface] + option.split())

            self.cli_set(self._base_path + [interface, 'min-links', str(min_links)])

        self.cli_commit()

        # verify config
        for interface in self._interfaces:
            tmp = get_interface_config(interface)

            self.assertEqual(min_links, tmp['linkinfo']['info_data']['min_links'])
            # check LACP default rate
            self.assertEqual('slow',    tmp['linkinfo']['info_data']['ad_lacp_rate'])

    def test_bonding_lacp_rate(self):
        # configure member interfaces
        lacp_rate = 'fast'
        for interface in self._interfaces:
            for option in self._options.get(interface, []):
                self.cli_set(self._base_path + [interface] + option.split())

            self.cli_set(self._base_path + [interface, 'lacp-rate', lacp_rate])

        self.cli_commit()

        # verify config
        for interface in self._interfaces:
            tmp = get_interface_config(interface)

            # check LACP minimum links (default value)
            self.assertEqual(0,         tmp['linkinfo']['info_data']['min_links'])
            self.assertEqual(lacp_rate, tmp['linkinfo']['info_data']['ad_lacp_rate'])

    def test_bonding_hash_policy(self):
        # Define available bonding hash policies
        hash_policies = ['layer2', 'layer2+3', 'encap2+3', 'encap3+4']
        for hash_policy in hash_policies:
            for interface in self._interfaces:
                for option in self._options.get(interface, []):
                    self.cli_set(self._base_path + [interface] + option.split())

                self.cli_set(self._base_path + [interface, 'hash-policy', hash_policy])

            self.cli_commit()

            # verify config
            for interface in self._interfaces:
                defined_policy = read_file(f'/sys/class/net/{interface}/bonding/xmit_hash_policy').split()
                self.assertEqual(defined_policy[0], hash_policy)

    def test_bonding_mii_monitoring_interval(self):
        for interface in self._interfaces:
            for option in self._options.get(interface, []):
                self.cli_set(self._base_path + [interface] + option.split())

        self.cli_commit()

        # verify default
        for interface in self._interfaces:
            tmp = read_file(f'/sys/class/net/{interface}/bonding/miimon').split()
            self.assertIn('100', tmp)

        mii_mon = '250'
        for interface in self._interfaces:
            self.cli_set(self._base_path + [interface, 'mii-mon-interval', mii_mon])

        self.cli_commit()

        # verify new CLI value
        for interface in self._interfaces:
            tmp = read_file(f'/sys/class/net/{interface}/bonding/miimon').split()
            self.assertIn(mii_mon, tmp)

    def test_bonding_multi_use_member(self):
        # Define available bonding hash policies
        for interface in ['bond10', 'bond20']:
            for member in self._members:
                self.cli_set(self._base_path + [interface, 'member', 'interface', member])

        # check validate() - can not use the same member interfaces multiple times
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(self._base_path + ['bond20'])

        self.cli_commit()

    def test_bonding_source_interface(self):
        # Re-use member interface that is already a source-interface
        bond = 'bond99'
        pppoe = 'pppoe98756'
        member = next(iter(self._members))

        self.cli_set(self._base_path + [bond, 'member', 'interface', member])
        self.cli_set(['interfaces', 'pppoe', pppoe, 'source-interface', member])

        # check validate() - can not add interface to bond, it is the source-interface of ...
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(['interfaces', 'pppoe', pppoe])
        self.cli_commit()

        # verify config
        slaves = read_file(f'/sys/class/net/{bond}/bonding/slaves').split()
        self.assertIn(member, slaves)

    def test_bonding_source_bridge_interface(self):
        # Re-use member interface that is already a source-interface
        bond = 'bond1097'
        bridge = 'br6327'
        member = next(iter(self._members))

        self.cli_set(self._base_path + [bond, 'member', 'interface', member])
        self.cli_set(['interfaces', 'bridge', bridge, 'member', 'interface', member])

        # check validate() - can not add interface to bond, it is a member of bridge ...
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(['interfaces', 'bridge', bridge])
        self.cli_commit()

        # verify config
        slaves = read_file(f'/sys/class/net/{bond}/bonding/slaves').split()
        self.assertIn(member, slaves)

    def test_bonding_uniq_member_description(self):
        ethernet_path = ['interfaces', 'ethernet']
        for interface in self._interfaces:
            for option in self._options.get(interface, []):
                self.cli_set(self._base_path + [interface] + option.split())

            self.cli_commit()

        # Add any changes on bonding members
        # For example add description on separate ethX interfaces
        for interface in self._interfaces:
            for member in self._members:
                self.cli_set(ethernet_path + [member, 'description', member + '_interface'])

            self.cli_commit()

        # verify config
        for interface in self._interfaces:
            slaves = read_file(f'/sys/class/net/{interface}/bonding/slaves').split()
            for member in self._members:
                self.assertIn(member, slaves)

    def test_bonding_system_mac(self):
        # configure member interfaces and system-mac
        default_system_mac = '00:00:00:00:00:00' # default MAC is all zeroes
        system_mac = '00:50:ab:cd:ef:11'

        for interface in self._interfaces:
            for option in self._options.get(interface, []):
                self.cli_set(self._base_path + [interface] + option.split())

            self.cli_set(self._base_path + [interface, 'system-mac', system_mac])

        self.cli_commit()

        # verify config
        for interface in self._interfaces:
            tmp = read_file(f'/sys/class/net/{interface}/bonding/ad_actor_system')
            self.assertIn(tmp, system_mac)

        for interface in self._interfaces:
            self.cli_delete(self._base_path + [interface, 'system-mac'])

        self.cli_commit()

        # verify default value
        for interface in self._interfaces:
            tmp = read_file(f'/sys/class/net/{interface}/bonding/ad_actor_system')
            self.assertIn(tmp, default_system_mac)

    def test_bonding_evpn_multihoming(self):
        id = '5'
        for interface in self._interfaces:
            for option in self._options.get(interface, []):
                self.cli_set(self._base_path + [interface] + option.split())

            self.cli_set(self._base_path + [interface, 'evpn', 'es-id', id])
            self.cli_set(self._base_path + [interface, 'evpn', 'es-df-pref', id])
            self.cli_set(self._base_path + [interface, 'evpn', 'es-sys-mac', f'00:12:34:56:78:0{id}'])
            self.cli_set(self._base_path + [interface, 'evpn', 'uplink'])

            id = int(id) + 1

        self.cli_commit()

        id = '5'
        for interface in self._interfaces:
            frrconfig = self.getFRRconfig(f'interface {interface}', daemon='zebra')

            self.assertIn(f' evpn mh es-id {id}', frrconfig)
            self.assertIn(f' evpn mh es-df-pref {id}', frrconfig)
            self.assertIn(f' evpn mh es-sys-mac 00:12:34:56:78:0{id}', frrconfig)
            self.assertIn(f' evpn mh uplink', frrconfig)

            id = int(id) + 1

        for interface in self._interfaces:
            self.cli_delete(self._base_path + [interface, 'evpn', 'es-id'])
            self.cli_delete(self._base_path + [interface, 'evpn', 'es-df-pref'])

        self.cli_commit()

        id = '5'
        for interface in self._interfaces:
            frrconfig = self.getFRRconfig(f'interface {interface}', daemon='zebra')
            self.assertIn(f' evpn mh es-sys-mac 00:12:34:56:78:0{id}', frrconfig)
            self.assertIn(f' evpn mh uplink', frrconfig)

            id = int(id) + 1

if __name__ == '__main__':
    unittest.main(verbosity=2)
