#!/usr/bin/env python3
#
# Copyright (C) VyOS Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os
import re
import unittest
from collections import defaultdict

from json import loads

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.cpu import get_available_cpus
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file
from vyos.utils.process import rc_cmd
from vyos.utils.system import sysctl_read
from vyos.utils.network import interface_exists
from vyos.system import image
from vyos.vpp import VPPControl
from vyos.vpp.utils import vpp_iface_name_transform
from vyos.vpp.config_resource_checks.resource_defaults import default_resource_map

PROCESS_NAME = 'vpp_main'
VPP_CONF = '/run/vpp/vpp.conf'
base_path = ['vpp']
resource_path = base_path + ['settings', 'resource-allocation']
interfaces_path = ['interfaces', 'vpp']
interface = 'eth1'


def get_vpp_config():
    config = defaultdict(dict)
    current_section = None

    with open(VPP_CONF, 'r') as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith('#'):  # Ignore empty lines and comments
                continue

            section_match = re.match(r'([a-zA-Z0-9_-]+)\s*{', line)
            if section_match:
                current_section = section_match.group(1)
                config[current_section] = {}
                continue

            if line == '}':  # End of section
                current_section = None
                continue

            key_value_match = re.match(r'([a-zA-Z0-9_-]+)\s+(.+)', line)
            if key_value_match:
                key, value = key_value_match.groups()
                if current_section:
                    config[current_section][key] = value
                else:
                    config[key] = value

    return config


def get_address(interface):
    rc, data = rc_cmd(f'ip --json address show dev {interface}')
    if rc == 0:
        data = loads(data)
        if isinstance(data, list) and len(data) > 0:
            ip_address = data[0]['addr_info'][0]['local']
            return ip_address


def get_vpp_cpu_allocation():
    reserved_cpus = default_resource_map.get('reserved_cpu_cores')
    # Get sorted list of available CPU IDs
    available = sorted({cpu['cpu'] for cpu in get_available_cpus()})
    main_core = available[reserved_cpus]  # first non-reserved CPU
    return reserved_cpus, main_core


class TestVPP(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestVPP, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)
        cls.cli_delete(cls, interfaces_path)

    def setUp(self):
        # always forward to base class
        super().setUp()

        self.cli_set(base_path + ['settings', 'interface', interface])
        self.cli_set(base_path + ['settings', 'poll-sleep-usec', '10'])

    def tearDown(self):
        try:
            # Check for running process
            self.assertTrue(process_named_running(PROCESS_NAME))
        finally:
            # Ensure these cleanup operations always run
            self.cli_delete(base_path)
            self.cli_delete(interfaces_path)
            self.cli_commit()

            # delete address for Ethernet interface
            self.cli_delete(['interfaces', 'ethernet', interface, 'address'])
            self.cli_commit()

        self.assertFalse(os.path.exists(VPP_CONF))
        self.assertFalse(process_named_running(PROCESS_NAME))
        # always forward to base class
        super().tearDown()

    def test_01_vpp_basic(self):
        poll_sleep = '0'
        mtu = '2500'
        skip_cores, main_core = get_vpp_cpu_allocation()

        self.cli_set(base_path + ['settings', 'poll-sleep-usec', poll_sleep])

        # commit changes
        self.cli_commit()

        config_entries = (
            f'poll-sleep-usec {poll_sleep}',
            f'skip-cores {skip_cores}',
            f'main-core {main_core}',
            'plugin default { disable }',
            'plugin dpdk_plugin.so { enable }',
            'plugin linux_cp_plugin.so { enable }',
            'plugin dhcp_plugin.so { enable }',
            'dev 0000:00:00.0',
            'uio-bind-force',
        )

        # Check configured options
        config = read_file(VPP_CONF)
        for config_entry in config_entries:
            self.assertIn(config_entry, config)

        # route-no-paths is not present in the output
        # looks like vpp bug
        _, out = rc_cmd('sudo vppctl show lcp')
        required_str = 'lcp route-no-paths on'
        self.assertIn(required_str, out)

        self.cli_set(base_path + ['settings', 'ignore-kernel-routes'])
        self.cli_commit()

        # check disabled 'route no path'
        _, out = rc_cmd('sudo vppctl show lcp')
        required_str = 'lcp route-no-paths off'
        self.assertIn(required_str, out)

        # set interface MTU
        self.cli_set(['interfaces', 'ethernet', interface, 'mtu', mtu])
        self.cli_commit()

        # check MTU for the LCP interface pair
        _, out = rc_cmd('sudo vppctl show interface')
        normalized_out = re.sub(r'\s+', ' ', out)
        self.assertIn(f'tap4096 2 up {mtu}/0/0/0', normalized_out)

        # delete mtu settings
        self.cli_delete(['interfaces', 'ethernet', interface, 'mtu'])
        self.cli_commit()

        # set interface address as dhcp
        self.cli_set(['interfaces', 'ethernet', interface, 'address', 'dhcp'])
        self.cli_commit()

        vpp = VPPControl()

        # check 'ip4-dhcp-client-detect' feature is enabled on interface
        client_detect_feature = vpp.api.feature_is_enabled(
            sw_if_index=vpp.get_sw_if_index(interface),
            feature_name='ip4-dhcp-client-detect',
            arc_name='ip4-unicast',
        )
        self.assertTrue(client_detect_feature.is_enabled)

        # set interface address as dhcpv6
        self.cli_set(['interfaces', 'ethernet', interface, 'address', 'dhcpv6'])
        self.cli_commit()

        # check 'ip6-icmp-ra-punt' feature is enabled on interface
        # for ip6-unicast and ip6-multicast arcs
        for arc_name in ['ip6-unicast', 'ip6-multicast']:
            icmpv6_ra_punt_feature = vpp.api.feature_is_enabled(
                sw_if_index=vpp.get_sw_if_index(interface),
                feature_name='ip6-icmp-ra-punt',
                arc_name=arc_name,
            )
            self.assertTrue(icmpv6_ra_punt_feature.is_enabled)

    def test_02_vpp_vxlan(self):
        vxlan_path = interfaces_path + ['vxlan']
        vni = '23'
        interface_vxlan = f'vppvxlan{vni}'
        source_address = '192.0.2.1'
        new_source_address = '192.0.2.3'
        remote_address = '192.0.2.254'
        address = '203.0.113.1'

        self.cli_set(['interfaces', 'ethernet', interface, 'address', '192.0.2.1/24'])
        self.cli_set(vxlan_path + [interface_vxlan, 'source-address', source_address])
        self.cli_set(vxlan_path + [interface_vxlan, 'vni', vni])

        # remote and source address must not be the same
        # expect raise ConfigError
        self.cli_set(vxlan_path + [interface_vxlan, 'remote', source_address])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(vxlan_path + [interface_vxlan, 'remote', remote_address])
        self.cli_set(vxlan_path + [interface_vxlan, 'address', f'{address}/24'])

        # commit changes
        self.cli_commit()

        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_vxlan}'))

        current_address = get_address(interface_vxlan)
        self.assertEqual(address, current_address)

        # check vxlan interface
        _, out = rc_cmd('sudo vppctl show vxlan tunnel')
        required_str = f'[0] instance 23 src {source_address} dst {remote_address} src_port 4789 dst_port 4789 vni {vni}'
        self.assertIn(required_str, out)

        # update vxlan interface
        self.cli_set(
            vxlan_path + [interface_vxlan, 'source-address', new_source_address]
        )

        # source address of the tunnel interface should be configured
        # expect raise ConfigError
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(
            [
                'interfaces',
                'ethernet',
                interface,
                'vif',
                vni,
                'address',
                f'{new_source_address}/24',
            ]
        )
        self.cli_commit()

        # check gre interface after update
        _, out = rc_cmd('sudo vppctl show vxlan tunnel')
        required_str = (
            f'[0] instance {vni} src {new_source_address} dst {remote_address}'
        )
        self.assertIn(required_str, out)
        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_vxlan}'))
        self.assertEqual(address, current_address)

        # change vpp settings
        self.cli_set(base_path + ['settings', 'poll-sleep-usec', '5'])
        self.cli_commit()

        config = read_file(VPP_CONF)
        self.assertIn('poll-sleep-usec 5', config)

        # delete vxlan interface
        self.cli_delete(vxlan_path + [interface_vxlan])
        self.cli_commit()

        # delete vif Ethernet interface
        self.cli_delete(['interfaces', 'ethernet', interface, 'vif'])
        self.cli_commit()

    def test_03_vpp_gre(self):
        gre_path = interfaces_path + ['gre']
        interface_gre = 'vppgre12'
        source_address = '192.0.2.1'
        new_source_address = '192.0.2.2'
        remote_address = '192.0.2.254'
        address = '10.0.0.0'

        self.cli_set(gre_path + [interface_gre, 'source-address', source_address])
        self.cli_set(gre_path + [interface_gre, 'remote', remote_address])
        self.cli_set(gre_path + [interface_gre, 'address', f'{address}/31'])

        # source address of the tunnel interface should be configured
        # expect raise ConfigError
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(
            ['interfaces', 'ethernet', interface, 'address', f'{source_address}/24']
        )

        # commit changes
        self.cli_commit()

        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_gre}'))
        current_address = get_address(interface_gre)
        self.assertEqual(address, current_address)

        # check gre interface
        _, out = rc_cmd('sudo vppctl show gre tunnel')
        required_str = f'[0] instance 12 src {source_address} dst {remote_address}'
        self.assertIn(required_str, out)

        # update gre interface
        self.cli_set(gre_path + [interface_gre, 'source-address', new_source_address])

        self.cli_set(
            ['interfaces', 'ethernet', interface, 'address', f'{new_source_address}/24']
        )
        self.cli_commit()

        # check gre interface after update
        _, out = rc_cmd('sudo vppctl show gre tunnel')
        required_str = f'[0] instance 12 src {new_source_address} dst {remote_address}'
        self.assertIn(required_str, out)
        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_gre}'))
        self.assertEqual(address, current_address)

        # delete gre interface
        self.cli_delete(gre_path + [interface_gre])
        self.cli_commit()

    def test_04_vpp_loopback(self):
        loopback_path = interfaces_path + ['loopback']
        interface_loopback = 'vpplo11'
        address = '192.0.2.54'

        self.cli_set(loopback_path + [interface_loopback])
        self.cli_set(loopback_path + [interface_loopback, 'address', f'{address}/25'])

        # commit changes
        self.cli_commit()

        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_loopback}'))

        current_address = get_address(interface_loopback)
        self.assertEqual(address, current_address)

        # check loopback interface
        _, out = rc_cmd('sudo vppctl show interface loop11')
        required_str = 'loop11'
        self.assertIn(required_str, out)

        # delete loopback interface
        self.cli_delete(loopback_path + [interface_loopback])
        self.cli_commit()

    def test_05_vpp_bonding(self):
        bond_path = interfaces_path + ['bonding']
        interface_bond = 'vppbond23'
        hash = 'layer3+4'
        mode = '802.3ad'
        description = 'Interface-Bonding'
        vlans = ['123', '456']
        vlan_description = 'My-vlan-123'

        self.cli_set(bond_path + [interface_bond, 'member', 'interface', interface])
        self.cli_set(bond_path + [interface_bond, 'hash-policy', hash])
        self.cli_set(bond_path + [interface_bond, 'mode', mode])

        # commit changes
        self.cli_commit()

        # Check for interface state "BondEthernet23 up"
        _, out = rc_cmd('sudo vppctl show interface')
        # Normalize the output for consistent whitespace
        normalized_out = re.sub(r'\s+', ' ', out)
        self.assertRegex(
            normalized_out,
            r'BondEthernet23\s+\d+\s+up',
            "Interface BondEthernet23 is not in the expected state 'up'.",
        )

        self.cli_set(bond_path + [interface_bond, 'description', description])
        for vlan in vlans:
            self.cli_set(
                bond_path
                + [interface_bond, 'vif', vlan, 'description', vlan_description]
            )

        # commit changes
        self.cli_commit()

        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_bond}'))
        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_bond}.{vlan}'))

        current_alias = read_file(f'/sys/class/net/{interface_bond}/ifalias')
        vlan_alias = read_file(f'/sys/class/net/{interface_bond}.{vlan}/ifalias')
        self.assertEqual(current_alias, description)
        self.assertEqual(vlan_alias, vlan_description)

        # check bonding interface
        _, out = rc_cmd('sudo vppctl show bond details')
        required_enries = (
            'BondEthernet23',
            'mode: lacp',
            'load balance: l34',
            'number of active members: 0',
            'number of members: 1',
            f'{interface}',
            'device instance: 0',
            'interface id: 23',
        )
        for entry in required_enries:
            self.assertIn(entry, out)

        # check interface state
        _, out = rc_cmd('sudo vppctl show interface')
        # Normalize the output for consistent whitespace
        normalized_out = re.sub(r'\s+', ' ', out)
        # Check for interface state "BondEthernet23 up"
        self.assertRegex(
            normalized_out,
            r'BondEthernet23\s+\d+\s+up',
            "Interface BondEthernet23 is not in the expected state 'up'.",
        )

        # delete vpp interface vlan
        self.cli_delete(bond_path + [interface_bond, 'vif'])
        self.cli_commit()
        self.assertFalse(os.path.isdir(f'/sys/class/net/{interface_bond}.{vlan}'))

        # delete bonding interface
        self.cli_delete(bond_path)
        self.cli_commit()

        # check deleting bonding interface
        _, out = rc_cmd('sudo vppctl show interface')
        self.assertNotIn('BondEthernet23', out)

    def test_06_vpp_bridge(self):
        bridge_path = interfaces_path + ['bridge']
        fake_member = 'eth2'
        members = [interface]
        interface_bridge = 'vppbr10'
        vni = '23'
        interface_vxlan = f'vppvxlan{vni}'
        source_address = '192.0.2.1'
        remote_address = '192.0.2.254'

        self.cli_set(['interfaces', 'ethernet', interface, 'address', '192.0.2.1/24'])
        for member in members:
            self.cli_set(
                bridge_path + [interface_bridge, 'member', 'interface', member]
            )

        # commit changes
        self.cli_commit()

        # check bridge interface
        _, out = rc_cmd('sudo vppctl show bridge-domain 10 detail')

        # Normalize the output for consistent whitespace
        normalized_out = re.sub(r'\s+', ' ', out)

        # Perform assertions based on the normalized output
        self.assertIn('BD-ID Index BSN Age(min)', normalized_out)
        self.assertIn('10 1 0 off', normalized_out)
        self.assertIn('Learning U-Forwrd UU-Flood Flooding', normalized_out)
        self.assertIn('on on flood on', normalized_out)
        self.assertIn('Interface If-idx ISN', normalized_out)
        # Check Interface, If-idx, ISN
        self.assertRegex(out, r'\s*eth1\s+\d+\s+\d+')

        # Set non exist member
        # expect raise ConfigError
        self.cli_set(
            bridge_path + [interface_bridge, 'member', 'interface', fake_member]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(
            bridge_path + [interface_bridge, 'member', 'interface', fake_member]
        )

        # Add VXLAN to the bridge
        self.cli_set(
            interfaces_path
            + ['vxlan', interface_vxlan, 'source-address', source_address]
        )
        self.cli_set(
            interfaces_path + ['vxlan', interface_vxlan, 'remote', remote_address]
        )
        self.cli_set(interfaces_path + ['vxlan', interface_vxlan, 'vni', vni])
        self.cli_set(
            bridge_path + [interface_bridge, 'member', 'interface', interface_vxlan]
        )

        # commit changes
        self.cli_commit()

        # check bridge interface
        _, out = rc_cmd('sudo vppctl show bridge-domain 10 detail')
        # Normalize the output for consistent whitespace
        normalized_out = re.sub(r'\s+', ' ', out)

        # Perform assertions based on the normalized output
        self.assertIn('BD-ID Index BSN Age(min)', normalized_out)
        self.assertRegex(normalized_out, r'10 1 \d+ off')
        self.assertIn('Learning U-Forwrd UU-Flood Flooding', normalized_out)
        self.assertIn('on on flood on', normalized_out)
        self.assertIn('Interface If-idx ISN', normalized_out)
        # Check Interface, If-idx, ISN
        self.assertRegex(out, r'\s*eth1\s+\d+\s+\d+')
        self.assertRegex(out, r'\s*vxlan_tunnel23\s+\d+\s+\d+')

        # Add check dependency ethernet => bridge
        self.cli_set(
            base_path + ['settings', 'interface', interface, 'num-rx-desc', '512']
        )
        self.cli_commit()
        # check bridge interface
        _, out = rc_cmd('sudo vppctl show bridge-domain 10 detail')
        # Normalize the output for consistent whitespace
        normalized_out = re.sub(r'\s+', ' ', out)
        self.assertRegex(out, r'\s*eth1\s+\d+\s+\d+')
        self.assertRegex(out, r'\s*vxlan_tunnel23\s+\d+\s+\d+')

        # Cannot add members of bridge interface to cross-connect
        # expect raise ConfigError
        self.cli_set(
            interfaces_path + ['xconnect', 'vppxcon1', 'member', 'interface', interface]
        )
        self.cli_set(
            interfaces_path
            + ['xconnect', 'vppxcon1', 'member', 'interface', interface_vxlan]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(interfaces_path + ['xconnect'])

        # Add Loopback BVI to the bridge
        self.cli_set(interfaces_path + ['loopback', f'vpplo{vni}'])
        self.cli_set(
            bridge_path
            + [interface_bridge, 'member', 'interface', f'vpplo{vni}', 'bvi']
        )
        # commit changes
        self.cli_commit()

        # check bridge interface
        _, out = rc_cmd('sudo vppctl show bridge-domain 10 detail')
        # Normalize the output for consistent whitespace
        normalized_out = re.sub(r'\s+', ' ', out)

        self.assertRegex(normalized_out, r'10 1 \d+ off')
        self.assertRegex(out, r'\bloop23\s+\d+\s+\d+\s+\d+\s+\*\s+')

    def test_07_vpp_ipip(self):
        ipip_path = interfaces_path + ['ipip']
        interface_ipip = 'vppipip12'
        source_address = '192.0.2.1'
        new_source_address = '192.0.2.2'
        remote_address = '192.0.2.5'
        address = '10.0.0.0'

        self.cli_set(['interfaces', 'ethernet', interface, 'address', '192.0.2.1/24'])
        self.cli_set(ipip_path + [interface_ipip, 'source-address', source_address])
        self.cli_set(ipip_path + [interface_ipip, 'remote', remote_address])
        self.cli_set(ipip_path + [interface_ipip, 'address', f'{address}/31'])

        # commit changes
        self.cli_commit()

        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_ipip}'))
        current_address = get_address(interface_ipip)
        self.assertEqual(address, current_address)

        # check ipip interface
        _, out = rc_cmd('sudo vppctl show ipip tunnel')
        required_str = f'[0] instance 12 src {source_address} dst {remote_address}'
        self.assertIn(required_str, out)

        # update ipip interface
        self.cli_set(ipip_path + [interface_ipip, 'source-address', new_source_address])

        # source address of the tunnel interface should be configured
        # expect raise ConfigError
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(
            ['interfaces', 'ethernet', interface, 'address', f'{new_source_address}/24']
        )
        self.cli_commit()

        # check ipip interface after update
        _, out = rc_cmd('sudo vppctl show ipip tunnel')
        required_str = f'[0] instance 12 src {new_source_address} dst {remote_address}'
        self.assertIn(required_str, out)
        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_ipip}'))
        self.assertEqual(address, current_address)

        # delete ipip interface
        self.cli_delete(ipip_path + [interface_ipip])
        self.cli_commit()

    def test_08_vpp_xconnect(self):
        xconn_path = interfaces_path + ['xconnect']
        vni = '23'
        interface_vxlan = f'vppvxlan{vni}'
        interface_xconnect = f'vppxcon{vni}'
        source_address = '192.0.2.1'
        remote_address = '192.0.2.254'

        self.cli_set(['interfaces', 'ethernet', interface, 'address', '192.0.2.1/24'])
        self.cli_set(
            interfaces_path
            + ['vxlan', interface_vxlan, 'source-address', source_address]
        )
        self.cli_set(
            interfaces_path + ['vxlan', interface_vxlan, 'remote', remote_address]
        )
        self.cli_set(interfaces_path + ['vxlan', interface_vxlan, 'vni', vni])

        # Add xconneect
        self.cli_set(
            xconn_path + [interface_xconnect, 'member', 'interface', interface]
        )

        # Cross connect interfaces require 2 interfaces
        # expect raise ConfigError
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(
            xconn_path + [interface_xconnect, 'member', 'interface', interface_vxlan]
        )

        # commit changes
        self.cli_commit()

        # check interface mode
        _, out = rc_cmd('sudo vppctl show mode')
        required_str_list = [
            f'l2 xconnect {interface} vxlan_tunnel{vni}',
            f'l2 xconnect vxlan_tunnel{vni} {interface}',
        ]
        for required_string in required_str_list:
            self.assertIn(required_string, out)

        # Cannot add members of cross-connect interface to bond/bridge
        # expect raise ConfigError
        self.cli_set(
            interfaces_path
            + ['bonding', 'vppbond1', 'member', 'interface', interface_vxlan]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(interfaces_path + ['bonding'])

        # delete xconnect interface
        self.cli_delete(xconn_path + [interface_xconnect])
        self.cli_commit()

        # check delete xconnect interface
        _, out = rc_cmd('sudo vppctl show mode')
        for required_string in required_str_list:
            self.assertNotIn(required_string, out)

    def test_09_vpp_driver_options(self):
        driver_options = {
            'num-rx-desc': '512',
            'num-tx-desc': '512',
            'num-rx-queues': '2',
            'num-tx-queues': '2',
        }
        cpu_cores = '2'

        base_interface_path = base_path + ['settings', 'interface', interface]

        for option, value in driver_options.items():
            self.cli_set(base_interface_path + [option, value])

        # rx/tx queue configuration expect VPP workers to be set
        # expect raise ConfigError
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(resource_path + ['cpu-cores', cpu_cores])

        # # DPDK driver expect only dpdk-options and not xdp-options to be set
        # # expect raise ConfigError
        # self.cli_set(base_interface_path + ['xdp-options', 'zero-copy'])
        #
        # with self.assertRaises(ConfigSessionError):
        #     self.cli_commit()
        #
        # # delete xdp-options and apply commit
        # self.cli_delete(base_interface_path + ['xdp-options'])

        self.cli_commit()

        # check dpdk options in config file
        config = read_file(VPP_CONF)

        for option, value in driver_options.items():
            self.assertIn(f'{option} {value}', config)

    def test_10_vpp_cpu_cores(self):
        cpu_cores = '2'
        skip_cores, main_core = get_vpp_cpu_allocation()

        # verify 'cpu-cores' are set not correctly
        # expect raise ConfigError
        self.cli_set(resource_path + ['cpu-cores', '99'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(resource_path + ['cpu-cores', cpu_cores])
        self.cli_commit()

        config_entries = (
            f'skip-cores {skip_cores}',  # reserved cpus skipped for system use
            f'main-core {main_core}',  # first available core is set as main-core
            f'workers {int(cpu_cores) - 1}',
            'dev 0000:00:00.0',
        )

        # Check configured options
        config = read_file(VPP_CONF)
        for config_entry in config_entries:
            self.assertIn(config_entry, config)

    def test_11_1_buffer_page_size(self):
        sizes = ['4K', '2M']
        for size in sizes:
            self.cli_set(resource_path + ['buffers', 'page-size', size])
            self.cli_commit()

            conf = get_vpp_config()
            self.assertEqual(conf['buffers']['page-size'], size)

    def test_11_2_statseg_page_size(self):
        sizes = ['4K', '2M']
        for size in sizes:
            self.cli_set(resource_path + ['memory', 'stats', 'page-size', size])
            self.cli_commit()

            conf = get_vpp_config()
            self.assertEqual(conf['statseg']['page-size'], size)

    def test_11_3_mem_page_size(self):
        sizes = ['4K', '2M']
        for size in sizes:
            self.cli_set(resource_path + ['memory', 'main-heap-page-size', size])
            self.cli_commit()

            conf = get_vpp_config()
            self.assertEqual(conf['memory']['main-heap-page-size'], size)

    def test_12_vpp_ipsec_xfrm_nl(self):
        rx_buffer_zise = default_resource_map.get('netlink_rx_buffer_size')

        self.cli_set(base_path + ['settings', 'ipsec-acceleration'])
        self.cli_commit()

        config_entries = (
            'linux-xfrm-nl',
            'enable-route-mode-ipsec',
            'interface ipsec',
            f'nl-rx-buffer-size {rx_buffer_zise}',
        )

        # Check configured options
        config = read_file(VPP_CONF)
        for config_entry in config_entries:
            self.assertIn(config_entry, config)

    def test_13_1_vpp_cgnat(self):
        base_cgnat = base_path + ['nat', 'cgnat']
        iface_out = 'eth0'
        iface_inside = 'eth1'
        timeout_udp = '150'
        timeout_icmp = '30'
        timeout_tcp_est = '600'
        timeout_tcp_trans = '120'
        inside_prefix = '100.64.0.0/24'
        outside_prefix = '192.0.2.1/32'

        self.cli_set(base_path + ['settings', 'interface', iface_out])
        self.cli_set(base_cgnat + ['interface', 'inside', iface_inside])
        self.cli_set(base_cgnat + ['interface', 'outside', iface_out])
        self.cli_set(base_cgnat + ['rule', '100', 'inside-prefix', inside_prefix])
        self.cli_set(base_cgnat + ['rule', '100', 'outside-prefix', outside_prefix])
        self.cli_set(base_cgnat + ['timeout', 'icmp', timeout_icmp])
        self.cli_set(base_cgnat + ['timeout', 'tcp-established', timeout_tcp_est])
        self.cli_set(base_cgnat + ['timeout', 'tcp-transitory', timeout_tcp_trans])
        self.cli_set(base_cgnat + ['timeout', 'udp', timeout_udp])
        self.cli_commit()

        # Check interfaces
        _, out = rc_cmd('sudo vppctl show det44 interfaces')
        self.assertIn(f'{iface_inside} in', out)
        self.assertIn(f'{iface_out} out', out)

        # Check mappings
        _, out = rc_cmd('sudo vppctl show det44 mappings')
        self.assertIn(inside_prefix, out)
        self.assertIn(outside_prefix, out)

        # Check timeouts
        _, out = rc_cmd('sudo vppctl show det44 timeouts')
        self.assertIn(f'udp timeout: {timeout_udp}sec', out)
        self.assertIn(f'tcp established timeout: {timeout_tcp_est}sec', out)
        self.assertIn(f'tcp transitory timeout: {timeout_tcp_trans}sec', out)
        self.assertIn(f'icmp timeout: {timeout_icmp}sec', out)

    def test_13_2_vpp_cgnat_bond_with_vifs(self):
        base_cgnat = base_path + ['nat', 'cgnat']
        base_bond = interfaces_path + ['bonding']
        iface_bond = 'vppbond0'
        vif_1 = '23'
        vif_2 = '24'
        iface_out = f'{iface_bond}.{vif_1}'
        iface_inside = f'{iface_bond}.{vif_2}'
        address_1 = '100.64.0.23/32'
        address_2 = '192.0.2.1/32'

        self.cli_set(base_bond + [iface_bond, 'member', 'interface', interface])
        self.cli_set(base_bond + [iface_bond, 'vif', vif_1, 'address', address_1])
        self.cli_set(base_bond + [iface_bond, 'vif', vif_2, 'address', address_2])

        self.cli_set(base_cgnat + ['interface', 'inside', iface_inside])
        self.cli_set(base_cgnat + ['interface', 'outside', iface_out])
        self.cli_set(base_cgnat + ['rule', '100', 'inside-prefix', address_1])
        self.cli_set(base_cgnat + ['rule', '100', 'outside-prefix', address_2])
        self.cli_commit()

        # Check interfaces
        _, out = rc_cmd('sudo vppctl show det44 interfaces')
        self.assertIn(f'BondEthernet0.{vif_2} in', out)
        self.assertIn(f'BondEthernet0.{vif_1} out', out)

        # Change bonding interface configuration
        self.cli_set(base_bond + [iface_bond, 'mode', '802.3ad'])
        self.cli_commit()

        # Check interfaces
        _, out = rc_cmd('sudo vppctl show det44 interfaces')
        self.assertIn(f'BondEthernet0.{vif_2} in', out)
        self.assertIn(f'BondEthernet0.{vif_1} out', out)

        # Verify only expected interfaces are shown:
        # header + inside + outside = 3 lines total
        lines = out.split('\n')
        self.assertTrue(len(lines) == 3)

        # Cannot remove inside/outside interface from vpp while it is used in the feature
        # expect raise ConfigError
        self.cli_delete(base_bond + [iface_bond, 'vif', vif_1])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_discard()

    def test_14_vpp_nat44(self):
        base_nat = base_path + ['nat', 'nat44']
        exclude_local_addr = '100.64.0.52'
        exclude_local_port = '22'
        iface_out = 'eth0'
        iface_inside = 'eth1'
        timeout_udp = '150'
        timeout_icmp = '30'
        timeout_tcp_est = '600'
        timeout_tcp_trans = '120'
        translation_pool = '192.0.2.1-192.0.2.2'
        static_ext_addr = '192.0.2.55'
        static_local_addr = '100.64.0.55'
        sess_limit = '64000'

        self.cli_set(base_path + ['settings', 'interface', iface_out])
        self.cli_set(base_nat + ['interface', 'inside', iface_inside])
        self.cli_set(base_nat + ['interface', 'outside', iface_out])
        self.cli_set(
            base_nat + ['address-pool', 'translation', 'address', translation_pool]
        )
        self.cli_commit()

        # Forwarding is disabled when only dynamic NAT is configured
        vpp = VPPControl()
        out = vpp.api.nat44_show_running_config().forwarding_enabled
        self.assertFalse(out)

        self.cli_set(
            base_nat + ['exclude', 'rule', '100', 'local-address', exclude_local_addr]
        )
        self.cli_set(
            base_nat + ['exclude', 'rule', '100', 'local-port', exclude_local_port]
        )

        # cannot set local-port without specifying protocol
        # expect raise ConfigError
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_nat + ['exclude', 'rule', '100', 'protocol', 'tcp'])
        self.cli_set(
            base_nat + ['static', 'rule', '100', 'external', 'address', static_ext_addr]
        )
        self.cli_set(
            base_nat + ['static', 'rule', '100', 'local', 'address', static_local_addr]
        )

        self.cli_set(base_nat + ['session-limit', sess_limit])
        self.cli_set(base_nat + ['timeout', 'icmp', timeout_icmp])
        self.cli_set(base_nat + ['timeout', 'tcp-established', timeout_tcp_est])
        self.cli_set(base_nat + ['timeout', 'tcp-transitory', timeout_tcp_trans])
        self.cli_set(base_nat + ['timeout', 'udp', timeout_udp])
        self.cli_commit()

        # Check addresses
        _, out = rc_cmd('sudo vppctl show nat44 addresses')
        self.assertIn(translation_pool.split('-')[0], out)
        self.assertIn(translation_pool.split('-')[1], out)

        # Check interfaces
        _, out = rc_cmd('sudo vppctl show nat44 interfaces')
        self.assertIn(f'{iface_inside} in', out)
        self.assertIn(f'{iface_out} out', out)

        # Check mappings
        _, out = rc_cmd('sudo vppctl show nat44 static mappings')
        self.assertIn(
            f'local {static_local_addr} external {static_ext_addr} vrf 0', out
        )
        self.assertIn(f'{exclude_local_addr}:{exclude_local_port} vrf 0', out)

        # Check timeouts
        _, out = rc_cmd('sudo vppctl show nat timeouts')
        self.assertIn(f'udp timeout: {timeout_udp}sec', out)
        self.assertIn(f'tcp-established timeout: {timeout_tcp_est}sec', out)
        self.assertIn(f'tcp-transitory timeout: {timeout_tcp_trans}sec', out)
        self.assertIn(f'icmp timeout: {timeout_icmp}sec', out)

        # Summary
        _, out = rc_cmd('sudo vppctl show nat44 summary')
        self.assertIn(f'max translations per thread: {sess_limit} fib 0', out)

        # Forwarding should be disabled with statyc+dynamic NAT
        vpp = VPPControl()
        out = vpp.api.nat44_show_running_config().forwarding_enabled
        self.assertFalse(out)

        # Delete dynamic NAT and check forwarding
        self.cli_delete(base_nat + ['address-pool'])
        self.cli_commit()

        # Forwarding should be enabled if only statyc NAT is configured
        vpp = VPPControl()
        out = vpp.api.nat44_show_running_config().forwarding_enabled
        self.assertTrue(out)

    def test_15_vpp_sflow(self):
        base_sflow = ['system', 'sflow']
        sampling_rate = '1500'
        polling_interval = '55'
        header_bytes = '256'
        iface_2 = 'eth0'

        self.cli_set(base_path + ['sflow', 'interface', interface])
        self.cli_set(base_path + ['sflow', 'header-bytes', header_bytes])
        self.cli_set(base_sflow + ['interface', interface])
        self.cli_set(base_sflow + ['server', '127.0.0.1'])
        self.cli_set(base_sflow + ['sampling-rate', sampling_rate])
        self.cli_set(base_sflow + ['polling', polling_interval])
        self.cli_set(base_sflow + ['vpp'])
        self.cli_commit()

        # Check sFlow
        _, out = rc_cmd('sudo vppctl show sflow')

        expected_entries = (
            f'sflow sampling-rate {sampling_rate}',
            'sflow direction rx',
            f'sflow polling-interval {polling_interval}',
            f'sflow header-bytes {header_bytes}',
            f'sflow enable {interface}',
            'interfaces enabled: 1',
        )

        for expected_entry in expected_entries:
            self.assertIn(expected_entry, out)

        self.cli_set(base_path + ['settings', 'interface', iface_2])
        self.cli_set(base_path + ['sflow', 'interface', iface_2])

        self.cli_commit()

        # Check sFlow
        _, out = rc_cmd('sudo vppctl show sflow')

        expected_entries = (
            f'sflow enable {interface}',
            f'sflow enable {iface_2}',
            'interfaces enabled: 2',
        )

        for expected_entry in expected_entries:
            self.assertIn(expected_entry, out)

        # Cannot remove interface from vpp while it is used in the feature
        # expect raise ConfigError
        self.cli_delete(base_path + ['settings', 'interface', iface_2])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_discard()

        # cannot delete system sFlow configuration if VPP sFlow is configured
        # expect raise ConfigError
        self.cli_delete(base_sflow)
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(base_path + ['sflow'])
        self.cli_commit()

        # Check interfaces are deleted from VPP sFlow
        _, out = rc_cmd('sudo vppctl show sflow')
        self.assertIn('interfaces enabled: 0', out)

    def test_16_resource_limits(self):
        max_map_count = '100000'
        shmmax = '55555555555555'
        hr_path = ['system', 'option', 'resource-limits']

        # Check if max-map-count has default auto calculated value
        # but not less than '65530'
        self.assertEqual(sysctl_read('vm.max_map_count'), '65530')
        # The same is with: kernel.shmmax = '8589934592'
        self.assertEqual(sysctl_read('kernel.shmmax'), '8589934592')

        # Change max-map-count, shmmax and check
        self.cli_set(hr_path + ['max-map-count', max_map_count])
        self.cli_set(hr_path + ['shmmax', shmmax])
        self.cli_commit()

        self.assertEqual(sysctl_read('vm.max_map_count'), max_map_count)
        self.assertEqual(sysctl_read('kernel.shmmax'), shmmax)

        # We expect max-map-count and shmmax will return auto calculated values
        self.cli_delete(hr_path + ['max-map-count'])
        self.cli_delete(hr_path + ['shmmax'])
        self.cli_commit()

        self.assertEqual(sysctl_read('vm.max_map_count'), '65530')
        self.assertEqual(sysctl_read('kernel.shmmax'), '8589934592')

    def test_17_1_vpp_pppoe_mapping(self):
        config_file = '/run/accel-pppd/pppoe.conf'
        pool = "TEST-POOL"
        vni = '23'
        pppoe_base = ['service', 'pppoe-server']

        self.cli_set(['interfaces', 'ethernet', interface, 'vif', vni])

        # Basic pppoe-server config
        self.cli_set(pppoe_base + ['authentication', 'mode', 'noauth'])
        self.cli_set(pppoe_base + ['gateway-address', '192.0.2.1'])
        self.cli_set(pppoe_base + ['client-ip-pool', pool, 'range', '192.0.2.0/24'])
        self.cli_set(pppoe_base + ['default-pool', pool])

        self.cli_set(pppoe_base + ['interface', interface])
        self.cli_set(pppoe_base + ['interface', f'{interface}.{vni}'])

        self.cli_commit()

        # Validate configuration values
        config = read_file(config_file)

        # Validate configuration
        # PPPoE on VPP-managed interfaces automatically get control-plane integration
        self.assertIn(f'interface={interface},vpp-cp=true', config)
        self.assertIn(f'interface={interface}.{vni},vpp-cp=true', config)

        # Check pppoe mapping
        _, out = rc_cmd('sudo vppctl show pppoe control-plane binding')
        self.assertRegex(out, rf'{interface}\s+tap4096')
        self.assertRegex(out, rf'{interface}.{vni}\s+tap4096.23')

        # check if dependency is called and mapping is correct after changes in vpp script
        self.cli_set(
            base_path + ['settings', 'interface', interface, 'num-tx-desc', '512']
        )
        self.cli_commit()

        # Check pppoe mapping
        _, out = rc_cmd('sudo vppctl show pppoe control-plane binding')
        self.assertRegex(out, rf'{interface}\s+tap4096')
        self.assertRegex(out, rf'{interface}.{vni}\s+tap4096.23')

        # delete PPPoE config
        self.cli_delete(pppoe_base)

        # delete vif Ethernet interface
        self.cli_delete(['interfaces', 'ethernet', interface, 'vif'])
        self.cli_commit()

    def test_17_2_vpp_pppoe_invalid_vif(self):
        # Test verify step behavior when referenced PPPoE interface does not actually exist
        pool = "TEST-POOL-2"
        vni = '24'
        pppoe_base = ['service', 'pppoe-server']

        # Basic pppoe-server config
        self.cli_set(pppoe_base + ['authentication', 'mode', 'noauth'])
        self.cli_set(pppoe_base + ['gateway-address', '192.0.3.1'])
        self.cli_set(pppoe_base + ['client-ip-pool', pool, 'range', '192.0.3.0/24'])
        self.cli_set(pppoe_base + ['default-pool', pool])

        self.cli_set(pppoe_base + ['interface', interface, 'combined'])
        self.cli_set(pppoe_base + ['interface', f'{interface}.{vni}'])

        err_msg = f'Virtual Interface "{interface}.{vni}" does not exist'
        with self.assertRaisesRegex(ConfigSessionError, err_msg):
            self.cli_commit()

        # The second commit can throw exception instead of verify error:
        #   - `FileNotFoundError: PCI device tap does not exist`
        # More details here: https://vyos.dev/T8276
        with self.assertRaisesRegex(ConfigSessionError, err_msg):
            self.cli_commit()
        self.assertTrue(interface_exists(interface))

        self.cli_set(['interfaces', 'ethernet', interface, 'vif', vni])
        self.cli_commit()

        # Cleanup PPPoE server configuration and created VIF
        self.cli_delete(pppoe_base)
        self.cli_delete(['interfaces', 'ethernet', interface, 'vif', vni])
        self.cli_commit()

    def test_17_3_vpp_pppoe_delete_invalid_vif(self):
        # Test verify step behavior when referenced PPPoE virtual interface was deleted
        pool = "TEST-POOL-3"
        vni = '25'
        pppoe_base = ['service', 'pppoe-server']

        # Basic pppoe-server config
        self.cli_set(pppoe_base + ['authentication', 'mode', 'noauth'])
        self.cli_set(pppoe_base + ['gateway-address', '192.0.4.1'])
        self.cli_set(pppoe_base + ['client-ip-pool', pool, 'range', '192.0.4.0/24'])
        self.cli_set(pppoe_base + ['default-pool', pool])
        self.cli_set(pppoe_base + ['interface', interface, 'combined'])
        self.cli_set(pppoe_base + ['interface', f'{interface}.{vni}'])

        err_msg = f'Virtual Interface "{interface}.{vni}" does not exist'
        with self.assertRaisesRegex(ConfigSessionError, err_msg):
            self.cli_commit()

        self.cli_delete(pppoe_base + ['interface', f'{interface}.{vni}'])
        self.cli_commit()

        # Cleanup PPPoE server configuration and created VIF
        self.cli_delete(pppoe_base)
        self.cli_commit()

    def test_17_4_vpp_pppoe_invalid_sub_vif(self):
        # Test verify step behavior when referenced PPPoE
        # sub-interface which have several tags does not exist
        pool = "TEST-POOL-4"
        vif_s, vif_c = '26', '10'
        pppoe_base = ['service', 'pppoe-server']

        # Basic pppoe-server config
        self.cli_set(pppoe_base + ['authentication', 'mode', 'noauth'])
        self.cli_set(pppoe_base + ['gateway-address', '192.0.5.1'])
        self.cli_set(pppoe_base + ['client-ip-pool', pool, 'range', '192.0.5.0/24'])
        self.cli_set(pppoe_base + ['default-pool', pool])

        self.cli_set(pppoe_base + ['interface', interface, 'combined'])
        self.cli_set(pppoe_base + ['interface', f'{interface}.{vif_s}.{vif_c}'])

        err_msg = f'Virtual Interface "{interface}.{vif_s}.{vif_c}" does not exist'
        with self.assertRaisesRegex(ConfigSessionError, err_msg):
            self.cli_commit()

        # The second commit can throw exception instead of verify error:
        #   - `FileNotFoundError: PCI device tap does not exist`
        # More details here: https://vyos.dev/T8276
        with self.assertRaisesRegex(ConfigSessionError, err_msg):
            self.cli_commit()
        self.assertTrue(interface_exists(interface))

        self.cli_set(
            ['interfaces', 'ethernet', interface, 'vif-s', vif_s, 'vif-c', vif_c]
        )
        self.cli_commit()

        # Cleanup PPPoE server configuration and created VIF
        self.cli_delete(pppoe_base)
        self.cli_delete(['interfaces', 'ethernet', interface, 'vif-s', vif_s])
        self.cli_commit()

    def test_18_kernel_options_hugepages(self):
        default_hp_size = '2M'
        hp_size_1g = '1G'
        hp_size_2m = '2M'
        hp_count_1g = '2'
        hp_count_2m = '512'
        memory_path = ['system', 'option', 'kernel', 'memory']

        self.cli_set(memory_path + ['default-hugepage-size', default_hp_size])
        self.cli_set(
            memory_path + ['hugepage-size', hp_size_2m, 'hugepage-count', hp_count_2m]
        )
        self.cli_set(
            memory_path + ['hugepage-size', hp_size_1g, 'hugepage-count', '2000']
        )
        # very big number of 1G hugepages, not enough memory for configuring them
        # expect raise ConfigError
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(
            memory_path + ['hugepage-size', hp_size_1g, 'hugepage-count', hp_count_1g]
        )
        self.cli_commit()

        # Read GRUB config file for current running image
        tmp = read_file(
            f'{image.grub.GRUB_DIR_VYOS_VERS}/{image.get_running_image()}.cfg'
        )
        self.assertIn(f' default_hugepagesz={default_hp_size}', tmp)
        self.assertIn(f' hugepagesz={hp_size_1g} hugepages={hp_count_1g}', tmp)
        self.assertIn(f' hugepagesz={hp_size_2m} hugepages={hp_count_2m}', tmp)

    def test_19_static_arp(self):
        host = '192.0.2.10'
        mac = '00:01:02:03:04:0a'
        path_static_arp = ['protocols', 'static', 'arp']

        self.cli_set(['interfaces', 'ethernet', interface, 'address', '192.0.2.1/24'])
        self.cli_set(
            path_static_arp + ['interface', interface, 'address', host, 'mac', mac]
        )
        self.cli_commit()

        # Change VPP configuration
        self.cli_set(base_path + ['settings', 'poll-sleep-usec', '50'])

        # Ensure arp entry is not disappeared
        _, neighbors = rc_cmd('sudo ip neighbor')
        self.assertIn(f'{host} dev {interface} lladdr {mac}', neighbors)

        # Check VPP IP neighbors
        _, vpp_neighbors = rc_cmd('sudo vppctl show ip neighbors')
        self.assertRegex(vpp_neighbors, rf'{host}\s+S\s+{mac}\s+{interface}')

        self.cli_delete(path_static_arp)

    def test_20_1_vpp_ipfix(self):
        base_ipfix = base_path + ['ipfix']
        base_collector = base_ipfix + ['collector']
        collector_ip = '127.0.0.2'
        collector_src = '127.0.0.1'
        collector_port = '9374'
        timer_active = '8'
        timer_passive = '32'
        tmplt_interval = '4'
        flow_probe_rec = 'l3'
        not_vpp_interface = 'eth0'

        self.cli_set(base_ipfix + ['active-timeout', timer_active])
        self.cli_set(base_ipfix + ['inactive-timeout', timer_passive])
        self.cli_set(base_ipfix + ['flowprobe-record', flow_probe_rec])
        self.cli_set(base_ipfix + ['interface', interface])
        self.cli_set(base_collector + [collector_ip, 'source-address', collector_src])
        self.cli_set(base_collector + [collector_ip, 'port', collector_port])
        self.cli_set(
            base_collector + [collector_ip, 'template-interval', tmplt_interval]
        )
        self.cli_commit()

        # Test 1: Verify flowprobe parameters
        _, out = rc_cmd('sudo vppctl show flowprobe params')
        required_str = (
            f'{flow_probe_rec} active: {timer_active} passive: {timer_passive}'
        )
        self.assertIn(required_str, out)

        # Test 2: Add non-VPP interface
        self.cli_set(base_ipfix + ['interface', not_vpp_interface])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(base_ipfix + ['interface', not_vpp_interface])
        self.cli_set(base_ipfix + ['interface', interface])
        self.cli_commit()

        _, out = rc_cmd('sudo vppctl show flowprobe feature')
        required_str = f'{interface} ip4 rx tx'
        self.assertIn(required_str, out)

        # Test 3: Verify IPFIX exporter via API
        # Set socket permissions to allow test access (owner/group read/write only)
        if os.path.exists('/run/vpp/api.sock'):
            os.system('sudo chmod 666 /run/vpp/api.sock')

        vpp = VPPControl()

        # Get all exporters
        result = vpp.api.ipfix_all_exporter_get()
        # Second element contains the exporter list
        exporters = result[1]

        # Find our configured exporter
        found_exporter = None
        for exporter in exporters:
            if str(exporter.collector_address) == collector_ip:
                found_exporter = exporter
                break

        # Verify exporter parameters
        self.assertIsNotNone(found_exporter, 'IPFIX exporter not found')
        self.assertEqual(str(found_exporter.collector_address), collector_ip)
        self.assertEqual(str(found_exporter.src_address), collector_src)
        self.assertEqual(found_exporter.collector_port, int(collector_port))
        self.assertEqual(found_exporter.template_interval, int(tmplt_interval))
        self.assertEqual(found_exporter.path_mtu, 512)  # Default path MTU
        self.assertEqual(found_exporter.vrf_id, 0)  # Default VRF
        self.assertFalse(found_exporter.udp_checksum)  # Default UDP checksum

        # Test 4: Cleanup - remove configuration
        self.cli_delete(base_ipfix)
        self.cli_commit()

        # Verify cleanup
        result = vpp.api.ipfix_all_exporter_get()
        exporters = result[1]
        # Should only have default exporter (0.0.0.0) left
        non_default_exporters = [
            e for e in exporters if str(e.collector_address) != '0.0.0.0'
        ]
        self.assertEqual(
            len(non_default_exporters), 0, 'Exporters not cleaned up properly'
        )

    def test_20_2_vpp_ipfix_bond(self):
        base_ipfix = base_path + ['ipfix']
        base_bond = interfaces_path + ['bonding']
        iface_bond = 'vppbond0'
        collector_ip = '127.0.0.2'
        collector_src = '127.0.0.1'

        self.cli_set(base_bond + [iface_bond, 'member', 'interface', interface])

        self.cli_set(
            base_ipfix + ['collector', collector_ip, 'source-address', collector_src]
        )
        self.cli_set(base_ipfix + ['interface', iface_bond])
        self.cli_commit()

        vpp_bond_name = vpp_iface_name_transform(iface_bond)
        required_str = f'{vpp_bond_name} ip4 rx tx'

        # Check bonding interface is added to IPFIX
        _, out = rc_cmd('sudo vppctl show flowprobe feature')
        self.assertIn(required_str, out)

        # Change bonding interface configuration
        self.cli_set(base_bond + [iface_bond, 'mode', '802.3ad'])
        self.cli_commit()

        # Check interface
        _, out = rc_cmd('sudo vppctl show flowprobe feature')
        self.assertIn(required_str, out)

    def test_21_double_enabling_vpp(self):
        # Verify double enabling of VPP

        # Delete already defined settings from 'setUp' method
        self.cli_delete(base_path)

        # First commit changes
        self.cli_set(base_path + ['settings', 'interface', interface])
        self.cli_set(base_path + ['settings', 'poll-sleep-usec', '20'])
        self.cli_commit()

        # Delete all VPP changes
        self.cli_delete(base_path)
        self.cli_commit()

        # Second commit changes
        self.cli_set(base_path + ['settings', 'interface', interface])
        self.cli_set(base_path + ['settings', 'poll-sleep-usec', '30'])
        self.cli_commit()

        # Ensure that VPP process is active
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_22_no_vpp_kernel_bridge_cross_membership(self):
        vlan = '123'
        member = f'{interface}.{vlan}'
        bridge_iface = 'br1'

        self.cli_commit()

        # Ensure that VPP process is active
        self.assertTrue(process_named_running(PROCESS_NAME))

        # Attempt to add a VPP interface VLAN as a bridge member
        self.cli_set(['interfaces', 'ethernet', interface, 'vif', vlan])
        self.cli_set(
            ['interfaces', 'bridge', bridge_iface, 'member', 'interface', member]
        )

        # Adding a VPP interface (or its VLAN) as a bridge member is not allowed
        # expect raise ConfigError
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(base_path)
        self.cli_commit()

        # Ensure interface is a member of bridge
        self.assertTrue(os.path.isdir(f'/sys/class/net/{bridge_iface}/lower_{member}'))

        # Adding a bridge member as a VPP interface is not allowed
        # expect raise ConfigError
        self.cli_set(base_path + ['settings', 'interface', interface])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(['interfaces', 'bridge'])
        self.cli_commit()

        # Ensure that VPP process is active
        self.assertTrue(process_named_running(PROCESS_NAME))


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
