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

import unittest

from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Interface
from vyos.ifconfig import Section
from vyos.utils.network import get_bridge_fdb
from vyos.utils.network import get_interface_config
from vyos.utils.network import interface_exists
from vyos.utils.network import get_vxlan_vlan_tunnels
from vyos.utils.network import get_vxlan_vni_filter
from vyos.template import is_ipv6
from base_interfaces_test import BasicInterfaceTest

def convert_to_list(ranges_to_convert):
    result_list = []
    for r in ranges_to_convert:
        ranges = r.split('-')
        result_list.extend([str(i) for i in range(int(ranges[0]), int(ranges[1]) + 1)])
    return result_list

class VXLANInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'vxlan']
        cls._options = {
            'vxlan10': ['vni 10', 'remote 127.0.0.2'],
            'vxlan20': ['vni 20', 'group 239.1.1.1', 'source-interface eth0', 'mtu 1450'],
            'vxlan30': ['vni 30', 'remote 2001:db8:2000::1', 'source-address 2001:db8:1000::1', 'parameters ipv6 flowlabel 0x1000'],
            'vxlan40': ['vni 40', 'remote 127.0.0.2', 'remote 127.0.0.3'],
            'vxlan50': ['vni 50', 'remote 2001:db8:2000::1', 'remote 2001:db8:2000::2', 'parameters ipv6 flowlabel 0x1000'],
        }
        cls._interfaces = list(cls._options)
        cls._mtu = '1450'
        # call base-classes classmethod
        super(VXLANInterfaceTest, cls).setUpClass()

    def test_vxlan_parameters(self):
        tos = '40'
        ttl = 20
        for intf in self._interfaces:
            for option in self._options.get(intf, []):
                self.cli_set(self._base_path + [intf] + option.split())

            self.cli_set(self._base_path + [intf, 'parameters', 'ip', 'df', 'set'])
            self.cli_set(self._base_path + [intf, 'parameters', 'ip', 'tos', tos])
            self.cli_set(self._base_path + [intf, 'parameters', 'ip', 'ttl', str(ttl)])
            ttl += 10

        self.cli_commit()

        ttl = 20
        for interface in self._interfaces:
            options = get_interface_config(interface)
            bridge = get_bridge_fdb(interface)

            vni = options['linkinfo']['info_data']['id']
            self.assertIn(f'vni {vni}', self._options[interface])

            if any('source-interface' in s for s in self._options[interface]):
                link = options['linkinfo']['info_data']['link']
                self.assertIn(f'source-interface {link}', self._options[interface])

            # Verify source-address setting was properly configured on the Kernel
            if any('source-address' in s for s in self._options[interface]):
                for s in self._options[interface]:
                    if 'source-address' in s:
                        address = s.split()[-1]
                        if is_ipv6(address):
                            tmp = options['linkinfo']['info_data']['local6']
                        else:
                            tmp = options['linkinfo']['info_data']['local']
                        self.assertIn(f'source-address {tmp}', self._options[interface])

            # Verify remote setting was properly configured on the Kernel
            if any('remote' in s for s in self._options[interface]):
                for s in self._options[interface]:
                    if 'remote' in s:
                        for fdb in bridge:
                            if 'mac' in fdb and fdb['mac'] == '00:00:00:00:00:00':
                                remote = fdb['dst']
                                self.assertIn(f'remote {remote}', self._options[interface])

            if any('group' in s for s in self._options[interface]):
                group = options['linkinfo']['info_data']['group']
                self.assertIn(f'group {group}', self._options[interface])

            if any('flowlabel' in s for s in self._options[interface]):
                label = options['linkinfo']['info_data']['label']
                self.assertIn(f'parameters ipv6 flowlabel {label}', self._options[interface])

            if any('external' in s for s in self._options[interface]):
                self.assertTrue(options['linkinfo']['info_data']['external'])

            self.assertEqual('vxlan',    options['linkinfo']['info_kind'])
            self.assertEqual('set',      options['linkinfo']['info_data']['df'])
            self.assertEqual(f'0x{tos}', options['linkinfo']['info_data']['tos'])
            self.assertEqual(ttl,        options['linkinfo']['info_data']['ttl'])
            self.assertEqual(Interface(interface).get_admin_state(), 'up')
            ttl += 10

    def test_vxlan_external(self):
        interface = 'vxlan0'
        source_address = '192.0.2.1'
        self.cli_set(self._base_path + [interface, 'parameters', 'external'])
        self.cli_set(self._base_path + [interface, 'source-address', source_address])

        # Both 'VNI' and 'external' can not be specified at the same time.
        self.cli_set(self._base_path + [interface, 'vni', '111'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(self._base_path + [interface, 'vni'])

        # Now add some more interfaces - this must fail and a CLI error needs
        # to be generated as Linux can only handle one VXLAN tunnel when using
        # external mode.
        for intf in self._interfaces:
            for option in self._options.get(intf, []):
                self.cli_set(self._base_path + [intf] + option.split())
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # Remove those test interfaces again
        for intf in self._interfaces:
            self.cli_delete(self._base_path + [intf])

        self.cli_commit()

        options = get_interface_config(interface)
        self.assertTrue(options['linkinfo']['info_data']['external'])
        self.assertEqual('vxlan',    options['linkinfo']['info_kind'])

    def test_vxlan_vlan_vni_mapping(self):
        bridge = 'br0'
        interface = 'vxlan0'
        source_address = '192.0.2.99'

        vlan_to_vni = {
            '10': '10010',
            '11': '10011',
            '12': '10012',
            '13': '10013',
            '20': '10020',
            '30': '10030',
            '31': '10031',
        }

        vlan_to_vni_ranges = {
            '40-43': '10040-10043',
            '45-47': '10045-10047'
        }

        self.cli_set(self._base_path + [interface, 'parameters', 'external'])
        self.cli_set(self._base_path + [interface, 'source-address', source_address])

        for vlan, vni in vlan_to_vni.items():
            self.cli_set(self._base_path + [interface, 'vlan-to-vni', vlan, 'vni', vni])

        # This must fail as this VXLAN interface is not associated with any bridge
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(['interfaces', 'bridge', bridge, 'member', 'interface', interface])

        # It is not allowed to use duplicate VNIs
        self.cli_set(self._base_path + [interface, 'vlan-to-vni', '11', 'vni', vlan_to_vni['10']])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        # restore VLAN - VNI mappings
        for vlan, vni in vlan_to_vni.items():
            self.cli_set(self._base_path + [interface, 'vlan-to-vni', vlan, 'vni', vni])

        # commit configuration
        self.cli_commit()

        self.assertTrue(interface_exists(bridge))
        self.assertTrue(interface_exists(interface))

        tmp = get_interface_config(interface)
        self.assertEqual(tmp['master'], bridge)
        self.assertFalse(tmp['linkinfo']['info_slave_data']['neigh_suppress'])

        tmp = get_vxlan_vlan_tunnels('vxlan0')
        self.assertEqual(tmp, list(vlan_to_vni))

        # add ranged VLAN - VNI mapping
        for vlan, vni in vlan_to_vni_ranges.items():
            self.cli_set(self._base_path + [interface, 'vlan-to-vni', vlan, 'vni', vni])
        self.cli_commit()

        tmp = get_vxlan_vlan_tunnels('vxlan0')
        vlans_list = convert_to_list(vlan_to_vni_ranges.keys())
        self.assertEqual(tmp, list(vlan_to_vni) + vlans_list)

        # check validate() - cannot map VNI range to a single VLAN id
        self.cli_set(self._base_path + [interface, 'vlan-to-vni', '100', 'vni', '100-102'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(self._base_path + [interface, 'vlan-to-vni', '100'])

        # check validate() - cannot map VLAN to VNI with different ranges
        self.cli_set(self._base_path + [interface, 'vlan-to-vni', '100-102', 'vni', '100-105'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(['interfaces', 'bridge', bridge])

    def test_vxlan_neighbor_suppress(self):
        bridge = 'br555'
        interface = 'vxlan555'
        source_interface = 'dum0'

        self.cli_set(['interfaces', Section.section(source_interface), source_interface, 'mtu', '9000'])

        self.cli_set(self._base_path + [interface, 'parameters', 'external'])
        self.cli_set(self._base_path + [interface, 'source-interface', source_interface])
        self.cli_set(self._base_path + [interface, 'parameters', 'neighbor-suppress'])

        # This must fail as this VXLAN interface is not associated with any bridge
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(['interfaces', 'bridge', bridge, 'member', 'interface', interface])

        # commit configuration
        self.cli_commit()

        self.assertTrue(interface_exists(bridge))
        self.assertTrue(interface_exists(interface))

        tmp = get_interface_config(interface)
        self.assertEqual(tmp['master'], bridge)
        self.assertTrue(tmp['linkinfo']['info_slave_data']['neigh_suppress'])
        self.assertFalse(tmp['linkinfo']['info_slave_data']['learning'])

        # Remove neighbor suppress configuration and re-test
        self.cli_delete(self._base_path + [interface, 'parameters', 'neighbor-suppress'])
        # commit configuration
        self.cli_commit()

        tmp = get_interface_config(interface)
        self.assertEqual(tmp['master'], bridge)
        self.assertFalse(tmp['linkinfo']['info_slave_data']['neigh_suppress'])
        self.assertTrue(tmp['linkinfo']['info_slave_data']['learning'])

        self.cli_delete(['interfaces', 'bridge', bridge])
        self.cli_delete(['interfaces', Section.section(source_interface), source_interface])

    def test_vxlan_vni_filter(self):
        interfaces = ['vxlan987', 'vxlan986', 'vxlan985']
        source_address = '192.0.2.77'

        for interface in interfaces:
            self.cli_set(self._base_path + [interface, 'parameters', 'external'])
            self.cli_set(self._base_path + [interface, 'source-address', source_address])

        # This must fail as there can only be one "external" VXLAN device unless "vni-filter" is defined
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # Enable "vni-filter" on the first VXLAN interface
        self.cli_set(self._base_path + [interfaces[0], 'parameters', 'vni-filter'])

        # This must fail as if it's enabled on one VXLAN interface, it must be enabled on all
        # VXLAN interfaces
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for interface in interfaces:
            self.cli_set(self._base_path + [interface, 'parameters', 'vni-filter'])

        # commit configuration
        self.cli_commit()

        for interface in interfaces:
            self.assertTrue(interface_exists(interface))

            tmp = get_interface_config(interface)
            self.assertTrue(tmp['linkinfo']['info_data']['vnifilter'])

    def test_vxlan_vni_filter_add_remove(self):
        interface = 'vxlan987'
        source_address = '192.0.2.66'
        bridge = 'br0'

        self.cli_set(self._base_path + [interface, 'parameters', 'external'])
        self.cli_set(self._base_path + [interface, 'source-address', source_address])
        self.cli_set(self._base_path + [interface, 'parameters', 'vni-filter'])

        # commit configuration
        self.cli_commit()

        # Check if VXLAN interface got created
        self.assertTrue(interface_exists(interface))

        # VNI filter configured?
        tmp = get_interface_config(interface)
        self.assertTrue(tmp['linkinfo']['info_data']['vnifilter'])

        # Now create some VLAN mappings and VNI filter
        vlan_to_vni = {
            '50': '10050',
            '51': '10051',
            '52': '10052',
            '53': '10053',
            '54': '10054',
            '60': '10060',
            '69': '10069',
        }

        vlan_to_vni_ranges = {
            '70-73': '10070-10073',
            '75-77': '10075-10077'
        }

        for vlan, vni in vlan_to_vni.items():
            self.cli_set(self._base_path + [interface, 'vlan-to-vni', vlan, 'vni', vni])
        # we need a bridge ...
        self.cli_set(['interfaces', 'bridge', bridge, 'member', 'interface', interface])
        # commit configuration
        self.cli_commit()

        # All VNIs configured?
        tmp = get_vxlan_vni_filter(interface)
        self.assertListEqual(list(vlan_to_vni.values()), tmp)

        #
        # Delete a VLAN mappings and check if all VNIs are properly set up
        #
        vlan_to_vni.popitem()
        self.cli_delete(self._base_path + [interface, 'vlan-to-vni'])
        for vlan, vni in vlan_to_vni.items():
            self.cli_set(self._base_path + [interface, 'vlan-to-vni', vlan, 'vni', vni])

        # commit configuration
        self.cli_commit()

        # All VNIs configured?
        tmp = get_vxlan_vni_filter(interface)
        self.assertListEqual(list(vlan_to_vni.values()), tmp)

        # add ranged VLAN - VNI mapping
        for vlan, vni in vlan_to_vni_ranges.items():
            self.cli_set(self._base_path + [interface, 'vlan-to-vni', vlan, 'vni', vni])
        self.cli_commit()

        tmp = get_vxlan_vni_filter(interface)
        vnis_list = convert_to_list(vlan_to_vni_ranges.values())
        self.assertListEqual(list(vlan_to_vni.values()) + vnis_list, tmp)

        self.cli_delete(['interfaces', 'bridge', bridge])

if __name__ == '__main__':
    unittest.main(verbosity=2)
