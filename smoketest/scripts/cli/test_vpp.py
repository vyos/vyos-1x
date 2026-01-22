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
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file
from vyos.utils.process import rc_cmd
from vyos.utils.system import sysctl_read
from vyos.system import image
from vyos.vpp import VPPControl
from vyos.vpp.utils import vpp_iface_name_transform

PROCESS_NAME = 'vpp_main'
VPP_CONF = '/run/vpp/vpp.conf'
base_path = ['vpp']
driver = 'dpdk'
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


class TestVPP(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestVPP, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def setUp(self):
        # always forward to base class
        super().setUp()

        self.cli_set(base_path + ['settings', 'interface', interface, 'driver', driver])
        self.cli_set(base_path + ['settings', 'unix', 'poll-sleep-usec', '10'])

    def tearDown(self):
        try:
            # Check for running process
            self.assertTrue(process_named_running(PROCESS_NAME))
        finally:
            # Ensure these cleanup operations always run
            self.cli_delete(base_path)
            self.cli_commit()

            # delete address for Ethernet interface
            self.cli_delete(['interfaces', 'ethernet', interface, 'address'])
            self.cli_commit()

        self.assertFalse(os.path.exists(VPP_CONF))
        self.assertFalse(process_named_running(PROCESS_NAME))
        # always forward to base class
        super().tearDown()

    def test_01_vpp_basic(self):
        main_core = '0'
        poll_sleep = '0'
        mtu = '2500'

        # Main core must be verified
        # expect raise ConfigError
        self.cli_set(base_path + ['settings', 'cpu', 'main-core', '99'])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['settings', 'cpu', 'main-core', main_core])
        self.cli_set(base_path + ['settings', 'unix', 'poll-sleep-usec', poll_sleep])

        # commit changes
        self.cli_commit()

        config_entries = (
            f'poll-sleep-usec {poll_sleep}',
            f'main-core {main_core}',
            'plugin default { disable }',
            'plugin dpdk_plugin.so { enable }',
            'plugin linux_cp_plugin.so { enable }',
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

        self.cli_set(base_path + ['settings', 'lcp', 'ignore-kernel-routes'])
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

    def test_02_vpp_vxlan(self):
        vni = '23'
        interface_vxlan = f'vxlan{vni}'
        interface_kernel = f'vpptap{vni}'
        new_interface_kernel = f'vpptap1{vni}'
        source_address = '192.0.2.1'
        new_source_address = '192.0.2.3'
        remote_address = '192.0.2.254'
        kernel_address = '203.0.113.1'

        self.cli_set(['interfaces', 'ethernet', interface, 'address', '192.0.2.1/24'])
        self.cli_set(
            base_path
            + ['interfaces', 'vxlan', interface_vxlan, 'source-address', source_address]
        )
        self.cli_set(base_path + ['interfaces', 'vxlan', interface_vxlan, 'vni', vni])

        # remote and source address must not be the same
        # expect raise ConfigError
        self.cli_set(
            base_path
            + ['interfaces', 'vxlan', interface_vxlan, 'remote', source_address]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(
            base_path
            + ['interfaces', 'vxlan', interface_vxlan, 'remote', remote_address]
        )
        self.cli_set(
            base_path
            + [
                'interfaces',
                'vxlan',
                interface_vxlan,
                'kernel-interface',
                interface_kernel,
            ]
        )
        self.cli_set(
            base_path
            + ['kernel-interfaces', interface_kernel, 'address', f'{kernel_address}/24']
        )

        # commit changes
        self.cli_commit()

        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_kernel}'))

        current_address = get_address(interface_kernel)
        self.assertEqual(kernel_address, current_address)

        # check vxlan interface
        _, out = rc_cmd('sudo vppctl show vxlan tunnel')
        required_str = f'[0] instance 23 src {source_address} dst {remote_address} src_port 4789 dst_port 4789 vni {vni}'
        self.assertIn(required_str, out)

        # update vxlan interface
        self.cli_set(
            base_path
            + [
                'interfaces',
                'vxlan',
                interface_vxlan,
                'source-address',
                new_source_address,
            ]
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
        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_kernel}'))
        self.assertEqual(kernel_address, current_address)

        # change vpp settings
        self.cli_set(base_path + ['settings', 'unix', 'poll-sleep-usec', '5'])
        self.cli_commit()

        config = read_file(VPP_CONF)
        self.assertIn('poll-sleep-usec 5', config)

        # delete vxlan kernel-interface but do not delete 'vpp kernel-interface'
        # expect raise ConfigError
        self.cli_delete(
            base_path
            + [
                'interfaces',
                'vxlan',
                interface_vxlan,
                'kernel-interface',
                interface_kernel,
            ]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # update vxlan kernel-interface but do not change 'vpp kernel-interface'
        # expect raise ConfigError
        self.cli_set(
            base_path
            + [
                'interfaces',
                'vxlan',
                interface_vxlan,
                'kernel-interface',
                new_interface_kernel,
            ]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # delete vpp kernel-interface
        self.cli_delete(base_path + ['kernel-interfaces', interface_kernel])
        self.cli_commit()

        # delete vxlan kernel-interface
        self.cli_delete(
            base_path + ['interfaces', 'vxlan', interface_vxlan, 'kernel-interface']
        )
        self.cli_commit()
        self.assertFalse(os.path.isdir(f'/sys/class/net/{interface_kernel}'))

        # delete vxlan interface
        self.cli_delete(base_path + ['interfaces', 'vxlan', interface_vxlan])
        self.cli_commit()

        # delete vif Ethernet interface
        self.cli_delete(['interfaces', 'ethernet', interface, 'vif'])
        self.cli_commit()

    def test_03_vpp_gre(self):
        interface_gre = 'gre12'
        interface_kernel = 'vpptun12'
        new_interface_kernel = 'vpptun123'
        source_address = '192.0.2.1'
        new_source_address = '192.0.2.2'
        remote_address = '192.0.2.254'
        kernel_address = '10.0.0.0'

        self.cli_set(
            base_path
            + ['interfaces', 'gre', interface_gre, 'source-address', source_address]
        )
        self.cli_set(
            base_path + ['interfaces', 'gre', interface_gre, 'remote', remote_address]
        )
        self.cli_set(
            base_path
            + ['interfaces', 'gre', interface_gre, 'kernel-interface', interface_kernel]
        )
        self.cli_set(
            base_path
            + ['kernel-interfaces', interface_kernel, 'address', f'{kernel_address}/31']
        )

        # source address of the tunnel interface should be configured
        # expect raise ConfigError
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(
            ['interfaces', 'ethernet', interface, 'address', f'{source_address}/24']
        )

        # commit changes
        self.cli_commit()

        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_kernel}'))
        current_address = get_address(interface_kernel)
        self.assertEqual(kernel_address, current_address)

        # check gre interface
        _, out = rc_cmd('sudo vppctl show gre tunnel')
        required_str = f'[0] instance 12 src {source_address} dst {remote_address}'
        self.assertIn(required_str, out)

        # update gre interface
        self.cli_set(
            base_path
            + ['interfaces', 'gre', interface_gre, 'source-address', new_source_address]
        )

        self.cli_set(
            ['interfaces', 'ethernet', interface, 'address', f'{new_source_address}/24']
        )
        self.cli_commit()

        # check gre interface after update
        _, out = rc_cmd('sudo vppctl show gre tunnel')
        required_str = f'[0] instance 12 src {new_source_address} dst {remote_address}'
        self.assertIn(required_str, out)
        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_kernel}'))
        self.assertEqual(kernel_address, current_address)

        # delete gre kernel-interface but do not delete 'vpp kernel-interface'
        # expect raise ConfigError
        self.cli_delete(
            base_path
            + ['interfaces', 'gre', interface_gre, 'kernel-interface', interface_kernel]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # update gre kernel-interface but do not change 'vpp kernel-interface'
        # expect raise ConfigError
        self.cli_set(
            base_path
            + [
                'interfaces',
                'gre',
                interface_gre,
                'kernel-interface',
                new_interface_kernel,
            ]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # delete kernel interface
        self.cli_delete(base_path + ['kernel-interfaces', interface_kernel])
        self.cli_commit()

        # delete gre kernel-interface
        self.cli_delete(
            base_path + ['interfaces', 'gre', interface_gre, 'kernel-interface']
        )
        self.cli_commit()
        self.assertFalse(os.path.isdir(f'/sys/class/net/{interface_kernel}'))

        # delete gre interface
        self.cli_delete(base_path + ['interfaces', 'gre', interface_gre])
        self.cli_commit()

    @unittest.skip('Skipping this test geneve index always is 0')
    def test_04_vpp_geneve(self):
        vni = '2'
        # Must be 'geneve0' to pass smoketest
        # As geneve interfaces cannot be named with "instance" suffix
        interface_geneve = 'geneve0'
        interface_kernel = f'vpptun{vni}'
        new_interface_kernel = f'vpptun1{vni}'
        source_address = '192.0.2.1'
        new_source_address = '192.0.2.2'
        remote_address = '203.0.113.10'
        kernel_address = '10.0.0.1'

        self.cli_set(
            base_path
            + [
                'interfaces',
                'geneve',
                interface_geneve,
                'source-address',
                source_address,
            ]
        )
        self.cli_set(
            base_path
            + ['interfaces', 'geneve', interface_geneve, 'remote', remote_address]
        )
        self.cli_set(base_path + ['interfaces', 'geneve', interface_geneve, 'vni', vni])
        self.cli_set(
            base_path
            + [
                'interfaces',
                'geneve',
                interface_geneve,
                'kernel-interface',
                interface_kernel,
            ]
        )
        self.cli_set(
            base_path
            + ['kernel-interfaces', interface_kernel, 'address', f'{kernel_address}/31']
        )

        # commit changes
        self.cli_commit()

        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_kernel}'))
        current_address = get_address(interface_kernel)
        self.assertEqual(kernel_address, current_address)

        # check geneve interface
        _, out = rc_cmd('sudo vppctl show geneve tunnel')
        required_str = f'[0] lcl {source_address} rmt {remote_address} vni {vni}'
        self.assertIn(required_str, out)

        # update geneve interface
        self.cli_set(
            base_path
            + [
                'interfaces',
                'geneve',
                interface_geneve,
                'source-address',
                new_source_address,
            ]
        )
        self.cli_commit()

        # check geneve interface after update
        _, out = rc_cmd('sudo vppctl show geneve tunnel')
        required_str = f'[0] lcl {new_source_address} rmt {remote_address} vni {vni}'
        self.assertIn(required_str, out)
        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_kernel}'))
        self.assertEqual(kernel_address, current_address)

        # delete geneve kernel-interface but do not delete 'vpp kernel-interface'
        # expect raise ConfigError
        self.cli_delete(
            base_path
            + [
                'interfaces',
                'geneve',
                interface_geneve,
                'kernel-interface',
                interface_kernel,
            ]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # update gemeve kernel-interface but do not change 'vpp kernel-interface'
        # expect raise ConfigError
        self.cli_set(
            base_path
            + [
                'interfaces',
                'geneve',
                interface_geneve,
                'kernel-interface',
                new_interface_kernel,
            ]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # delete vpp kernel-interface
        self.cli_delete(base_path + ['kernel-interfaces', interface_kernel])
        self.cli_commit()

        # delete geneve kernel-interface
        self.cli_delete(
            base_path + ['interfaces', 'geneve', interface_geneve, 'kernel-interface']
        )
        self.cli_commit()

        self.assertFalse(os.path.isdir(f'/sys/class/net/{interface_kernel}'))

        # delete geneve interface
        self.cli_set(base_path + ['interfaces', 'geneve', interface_geneve])
        self.cli_commit()

    def test_05_vpp_loopback(self):
        interface_loopback = 'lo11'
        interface_kernel = 'vpptun11'
        new_interface_kernel = 'vpptun12'
        kernel_address = '192.0.2.54'

        self.cli_set(base_path + ['interfaces', 'loopback', interface_loopback])
        self.cli_set(
            base_path
            + [
                'interfaces',
                'loopback',
                interface_loopback,
                'kernel-interface',
                interface_kernel,
            ]
        )
        self.cli_set(
            base_path
            + ['kernel-interfaces', interface_kernel, 'address', f'{kernel_address}/25']
        )

        # commit changes
        self.cli_commit()

        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_kernel}'))

        current_address = get_address(interface_kernel)
        self.assertEqual(kernel_address, current_address)

        # check loopback interface
        _, out = rc_cmd('sudo vppctl show interface loop11')
        required_str = 'loop11'
        self.assertIn(required_str, out)

        # delete loopback kernel-interface but do not delete 'vpp kernel-interface'
        # expect raise ConfigError
        self.cli_delete(
            base_path
            + [
                'interfaces',
                'loopback',
                interface_loopback,
                'kernel-interface',
                interface_kernel,
            ]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # update loopback kernel-interface but do not change 'vpp kernel-interface'
        # expect raise ConfigError
        self.cli_set(
            base_path
            + [
                'interfaces',
                'loopback',
                interface_loopback,
                'kernel-interface',
                new_interface_kernel,
            ]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # delete vpp kernel-interface
        self.cli_delete(base_path + ['kernel-interfaces', interface_kernel])
        self.cli_commit()

        # delete loopback kernel-interface
        self.cli_delete(
            base_path
            + ['interfaces', 'loopback', interface_loopback, 'kernel-interface']
        )
        self.cli_commit()
        self.assertFalse(os.path.isdir(f'/sys/class/net/{interface_kernel}'))

        # delete loopback interface
        self.cli_delete(base_path + ['interfaces', 'loopback', interface_loopback])
        self.cli_commit()

    def test_06_vpp_bonding(self):
        interface_bond = 'bond23'
        interface_kernel = 'vpptun23'
        hash = 'layer3+4'
        mode = '802.3ad'
        description = 'Interface-Bonding'
        vlans = ['123', '456']
        vlan_description = 'My-vlan-123'

        self.cli_set(
            base_path
            + [
                'interfaces',
                'bonding',
                interface_bond,
                'member',
                'interface',
                interface,
            ]
        )
        self.cli_set(
            base_path + ['interfaces', 'bonding', interface_bond, 'hash-policy', hash]
        )
        self.cli_set(
            base_path + ['interfaces', 'bonding', interface_bond, 'mode', mode]
        )

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

        # set kernel interface
        self.cli_set(
            base_path
            + [
                'interfaces',
                'bonding',
                interface_bond,
                'kernel-interface',
                interface_kernel,
            ]
        )
        self.cli_set(
            base_path
            + ['kernel-interfaces', interface_kernel, 'description', description]
        )
        for vlan in vlans:
            self.cli_set(
                base_path
                + [
                    'kernel-interfaces',
                    interface_kernel,
                    'vif',
                    vlan,
                    'description',
                    vlan_description,
                ]
            )

        # commit changes
        self.cli_commit()

        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_kernel}'))
        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_kernel}.{vlan}'))

        current_alias = read_file(f'/sys/class/net/{interface_kernel}/ifalias')
        vlan_alias = read_file(f'/sys/class/net/{interface_kernel}.{vlan}/ifalias')
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

        # delete vpp kernel-interface vlan
        self.cli_delete(base_path + ['kernel-interfaces', interface_kernel, 'vif'])
        self.cli_commit()
        self.assertFalse(os.path.isdir(f'/sys/class/net/{interface_kernel}.{vlan}'))

        # delete vpp kernel-interface
        self.cli_delete(base_path + ['kernel-interfaces', interface_kernel])
        self.cli_commit()

        # delete bonding kernel-interface
        self.cli_delete(
            base_path + ['interfaces', 'bonding', interface_bond, 'kernel-interface']
        )
        self.cli_commit()
        self.assertFalse(os.path.isdir(f'/sys/class/net/{interface_kernel}'))

        # delete bonding interface
        self.cli_delete(base_path + ['interfaces', 'bonding'])
        self.cli_commit()

        # check deleting bonding interface
        _, out = rc_cmd('sudo vppctl show interface')
        self.assertNotIn('BondEthernet23', out)

    def test_07_vpp_bridge(self):
        fake_member = 'eth2'
        members = [interface]
        interface_bridge = 'br10'
        vni = '23'
        interface_vxlan = f'vxlan{vni}'
        source_address = '192.0.2.1'
        remote_address = '192.0.2.254'

        self.cli_set(['interfaces', 'ethernet', interface, 'address', '192.0.2.1/24'])
        for member in members:
            self.cli_set(
                base_path
                + [
                    'interfaces',
                    'bridge',
                    interface_bridge,
                    'member',
                    'interface',
                    member,
                ]
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
            base_path
            + [
                'interfaces',
                'bridge',
                interface_bridge,
                'member',
                'interface',
                fake_member,
            ]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(
            base_path
            + [
                'interfaces',
                'bridge',
                interface_bridge,
                'member',
                'interface',
                fake_member,
            ]
        )

        # Add VXLAN to the bridge
        self.cli_set(
            base_path
            + ['interfaces', 'vxlan', interface_vxlan, 'source-address', source_address]
        )
        self.cli_set(
            base_path
            + ['interfaces', 'vxlan', interface_vxlan, 'remote', remote_address]
        )
        self.cli_set(base_path + ['interfaces', 'vxlan', interface_vxlan, 'vni', vni])
        self.cli_set(
            base_path
            + [
                'interfaces',
                'bridge',
                interface_bridge,
                'member',
                'interface',
                interface_vxlan,
            ]
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
        self.assertRegex(out, r'\s*vxlan_tunnel23\s+\d+\s+\d+')

        # Add check dependency ethernet => bridge
        self.cli_set(
            base_path + ['settings', 'interface', interface, 'dpdk-options', 'promisc']
        )
        self.cli_commit()
        # check bridge interface
        _, out = rc_cmd('sudo vppctl show bridge-domain 10 detail')
        # Normalize the output for consistent whitespace
        normalized_out = re.sub(r'\s+', ' ', out)
        self.assertRegex(out, r'\s*eth1\s+\d+\s+\d+')
        self.assertRegex(out, r'\s*vxlan_tunnel23\s+\d+\s+\d+')

        # Add Loopback BVI to the bridge
        self.cli_set(base_path + ['interfaces', 'loopback', f'lo{vni}'])
        self.cli_set(
            base_path
            + [
                'interfaces',
                'bridge',
                interface_bridge,
                'member',
                'interface',
                f'lo{vni}',
                'bvi',
            ]
        )
        # commit changes
        self.cli_commit()

        # check bridge interface
        _, out = rc_cmd('sudo vppctl show bridge-domain 10 detail')
        # Normalize the output for consistent whitespace
        normalized_out = re.sub(r'\s+', ' ', out)

        self.assertIn('10 1 0 off', normalized_out)
        self.assertRegex(out, r'\bloop23\s+\d+\s+\d+\s+\d+\s+\*\s+')

    def test_08_vpp_ipip(self):
        interface_ipip = 'ipip12'
        interface_kernel = 'vpptun12'
        new_interface_kernel = 'vpptun123'
        source_address = '192.0.2.1'
        new_source_address = '192.0.2.2'
        remote_address = '192.0.2.5'
        kernel_address = '10.0.0.0'

        self.cli_set(['interfaces', 'ethernet', interface, 'address', '192.0.2.1/24'])
        self.cli_set(
            base_path
            + ['interfaces', 'ipip', interface_ipip, 'source-address', source_address]
        )
        self.cli_set(
            base_path + ['interfaces', 'ipip', interface_ipip, 'remote', remote_address]
        )
        self.cli_set(
            base_path
            + [
                'interfaces',
                'ipip',
                interface_ipip,
                'kernel-interface',
                interface_kernel,
            ]
        )
        self.cli_set(
            base_path
            + ['kernel-interfaces', interface_kernel, 'address', f'{kernel_address}/31']
        )

        # commit changes
        self.cli_commit()

        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_kernel}'))
        current_address = get_address(interface_kernel)
        self.assertEqual(kernel_address, current_address)

        # check ipip interface
        _, out = rc_cmd('sudo vppctl show ipip tunnel')
        required_str = f'[0] instance 12 src {source_address} dst {remote_address}'
        self.assertIn(required_str, out)

        # update ipip interface
        self.cli_set(
            base_path
            + [
                'interfaces',
                'ipip',
                interface_ipip,
                'source-address',
                new_source_address,
            ]
        )

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
        self.assertTrue(os.path.isdir(f'/sys/class/net/{interface_kernel}'))
        self.assertEqual(kernel_address, current_address)

        # delete ipip kernel-interface but do not delete 'vpp kernel-interface'
        # expect raise ConfigError
        self.cli_delete(
            base_path
            + [
                'interfaces',
                'ipip',
                interface_ipip,
                'kernel-interface',
                interface_kernel,
            ]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # update ipip kernel-interface but do not change 'vpp kernel-interface'
        # expect raise ConfigError
        self.cli_set(
            base_path
            + [
                'interfaces',
                'ipip',
                interface_ipip,
                'kernel-interface',
                new_interface_kernel,
            ]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # delete kernel interface
        self.cli_delete(base_path + ['kernel-interfaces', interface_kernel])
        self.cli_commit()

        # delete ipip kernel-interface
        self.cli_delete(
            base_path + ['interfaces', 'ipip', interface_ipip, 'kernel-interface']
        )
        self.cli_commit()
        self.assertFalse(os.path.isdir(f'/sys/class/net/{interface_kernel}'))

        # delete ipip interface
        self.cli_delete(base_path + ['interfaces', 'ipip', interface_ipip])
        self.cli_commit()

    def test_09_vpp_xconnect(self):
        vni = '23'
        interface_vxlan = f'vxlan{vni}'
        interface_xconnect = f'xcon{vni}'
        source_address = '192.0.2.1'
        remote_address = '192.0.2.254'

        self.cli_set(['interfaces', 'ethernet', interface, 'address', '192.0.2.1/24'])
        self.cli_set(
            base_path
            + ['interfaces', 'vxlan', interface_vxlan, 'source-address', source_address]
        )
        self.cli_set(
            base_path
            + ['interfaces', 'vxlan', interface_vxlan, 'remote', remote_address]
        )
        self.cli_set(base_path + ['interfaces', 'vxlan', interface_vxlan, 'vni', vni])

        # Add xconneect
        self.cli_set(
            base_path
            + [
                'interfaces',
                'xconnect',
                interface_xconnect,
                'member',
                'interface',
                interface,
            ]
        )

        # Cross connect interfaces require 2 interfaces
        # expect raise ConfigError
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(
            base_path
            + [
                'interfaces',
                'xconnect',
                interface_xconnect,
                'member',
                'interface',
                interface_vxlan,
            ]
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

        # delete xconnect interface
        self.cli_delete(base_path + ['interfaces', 'xconnect', interface_xconnect])
        self.cli_commit()

        # check delete xconnect interface
        _, out = rc_cmd('sudo vppctl show mode')
        for required_string in required_str_list:
            self.assertNotIn(required_string, out)

    def test_10_vpp_driver_options(self):
        dpdk_options = {
            'num-rx-desc': '512',
            'num-tx-desc': '512',
            'num-rx-queues': '1',
            'num-tx-queues': '1',
        }
        main_core = '0'
        workers = '1'

        base_interface_path = base_path + ['settings', 'interface', interface]

        for option, value in dpdk_options.items():
            self.cli_set(base_interface_path + ['dpdk-options', option, value])

        # rx/tx queue configuration expect VPP workers to be set
        # expect raise ConfigError
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['settings', 'cpu', 'main-core', main_core])
        self.cli_set(base_path + ['settings', 'cpu', 'workers', workers])

        # DPDK driver expect only dpdk-options and not xdp-options to be set
        # expect raise ConfigError
        self.cli_set(base_interface_path + ['xdp-options', 'zero-copy'])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # delete xdp-options and apply commit
        self.cli_delete(base_interface_path + ['xdp-options'])
        self.cli_commit()

        # check dpdk options in config file
        config = read_file(VPP_CONF)

        for option, value in dpdk_options.items():
            self.assertIn(f'{option} {value}', config)

    def test_11_vpp_cpu_settings(self):
        main_core = '2'
        workers = '1'
        skip_cores = '1'

        self.cli_set(base_path + ['settings', 'cpu', 'workers', workers])

        # "cpu workers" reqiures main-core to be set
        # expect raise ConfigError
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['settings', 'cpu', 'main-core', main_core])

        self.cli_set(base_path + ['settings', 'cpu', 'skip-cores', '99'])

        # "cpu skip-cores" cannot be more than number of available CPUs - 1
        # expect raise ConfigError
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['settings', 'cpu', 'skip-cores', skip_cores])

        self.cli_commit()

        config_entries = (
            f'skip-cores {skip_cores}',
            f'main-core {main_core}',
            f'workers {workers}',
            'dev 0000:00:00.0',
        )

        # Check configured options
        config = read_file(VPP_CONF)
        for config_entry in config_entries:
            self.assertIn(config_entry, config)

    def test_12_vpp_cpu_corelist_workers(self):
        main_core = '0'
        corelist_workers = ['3']

        for worker in corelist_workers:
            self.cli_set(base_path + ['settings', 'cpu', 'corelist-workers', worker])

        # "cpu corelist-workers" reqiures main-core to be set
        # expect raise ConfigError
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['settings', 'cpu', 'main-core', main_core])

        # corelist-workers and workers cannot be used at the same time
        # expect raise ConfigError
        self.cli_set(base_path + ['settings', 'cpu', 'workers', '2'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['settings', 'cpu', 'workers'])

        # verify corelist-workers are set not correctly
        # expect raise ConfigError
        self.cli_set(base_path + ['settings', 'cpu', 'corelist-workers', '99-101'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(base_path + ['settings', 'cpu', 'corelist-workers', '99-101'])

        self.cli_commit()

        config_entries = (
            f'main-core {main_core}',
            f'corelist-workers {",".join(corelist_workers)}',
            'dev 0000:00:00.0',
        )

        # Check configured options
        config = read_file(VPP_CONF)
        for config_entry in config_entries:
            self.assertIn(config_entry, config)

    def test_13_1_buffer_page_size(self):
        sizes = ['4K', '2M']
        for size in sizes:
            self.cli_set(base_path + ['settings', 'buffers', 'page-size', size])
            self.cli_commit()

            conf = get_vpp_config()
            self.assertEqual(conf['buffers']['page-size'], size)

    def test_13_2_statseg_page_size(self):
        sizes = ['4K', '2M']
        for size in sizes:
            self.cli_set(base_path + ['settings', 'statseg', 'page-size', size])
            self.cli_commit()

            conf = get_vpp_config()
            self.assertEqual(conf['statseg']['page-size'], size)

    def test_13_3_mem_page_size(self):
        sizes = ['4K', '2M']
        for size in sizes:
            self.cli_set(
                base_path + ['settings', 'memory', 'main-heap-page-size', size]
            )
            self.cli_commit()

            conf = get_vpp_config()
            self.assertEqual(conf['memory']['main-heap-page-size'], size)

    def test_14_vpp_ipsec_xfrm_nl(self):
        base_ipsec = base_path + ['settings', 'ipsec']
        batch_delay = '250'
        batch_size = '150'
        rx_buffer_zise = '1024'

        self.cli_set(base_ipsec + ['netlink', 'batch-delay-ms', batch_delay])
        self.cli_set(base_ipsec + ['netlink', 'batch-size', batch_size])
        self.cli_set(base_ipsec + ['netlink', 'rx-buffer-size', rx_buffer_zise])
        self.cli_commit()

        config_entries = (
            'linux-xfrm-nl',
            'enable-route-mode-ipsec',
            'interface ipsec',
            f'nl-batch-delay-ms {batch_delay}',
            f'nl-batch-size {batch_size}',
            f'nl-rx-buffer-size {rx_buffer_zise}',
        )

        # Check configured options
        config = read_file(VPP_CONF)
        for config_entry in config_entries:
            self.assertIn(config_entry, config)

        # set IPsec tunnel-type ipip
        self.cli_set(base_ipsec + ['interface-type', 'ipip'])
        self.cli_commit()

        config = read_file(VPP_CONF)
        self.assertIn('interface ipip', config)

    def test_15_1_vpp_cgnat(self):
        base_cgnat = base_path + ['nat', 'cgnat']
        iface_out = 'eth0'
        iface_inside = 'eth1'
        timeout_udp = '150'
        timeout_icmp = '30'
        timeout_tcp_est = '600'
        timeout_tcp_trans = '120'
        inside_prefix = '100.64.0.0/24'
        outside_prefix = '192.0.2.1/32'

        self.cli_set(base_path + ['settings', 'interface', iface_out, 'driver', driver])
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

    def test_15_2_vpp_cgnat_bond_with_vifs(self):
        base_cgnat = base_path + ['nat', 'cgnat']
        base_kernel = base_path + ['kernel-interfaces']
        base_bond = base_path + ['interfaces', 'bonding']
        iface_kernel = 'vpptun0'
        iface_bond = 'bond0'
        vif_1 = '23'
        vif_2 = '24'
        iface_out = f'{iface_bond}.{vif_1}'
        iface_inside = f'{iface_bond}.{vif_2}'
        address_1 = '100.64.0.23/32'
        address_2 = '192.0.2.1/32'

        self.cli_set(base_bond + [iface_bond, 'kernel-interface', iface_kernel])
        self.cli_set(base_bond + [iface_bond, 'member', 'interface', interface])

        self.cli_set(base_kernel + [iface_kernel, 'vif', vif_1, 'address', address_1])
        self.cli_set(base_kernel + [iface_kernel, 'vif', vif_2, 'address', address_2])

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

    def test_16_vpp_nat(self):
        base_nat = base_path + ['nat44']
        base_nat_settings = base_path + ['settings', 'nat44']
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

        self.cli_set(base_path + ['settings', 'interface', iface_out, 'driver', driver])
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

        self.cli_set(base_nat_settings + ['session-limit', sess_limit])
        self.cli_set(base_nat_settings + ['timeout', 'icmp', timeout_icmp])
        self.cli_set(
            base_nat_settings + ['timeout', 'tcp-established', timeout_tcp_est]
        )
        self.cli_set(
            base_nat_settings + ['timeout', 'tcp-transitory', timeout_tcp_trans]
        )
        self.cli_set(base_nat_settings + ['timeout', 'udp', timeout_udp])
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

    def test_17_vpp_sflow(self):
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
            'sflow sampling-direction ingress',
            f'sflow polling-interval {polling_interval}',
            f'sflow header-bytes {header_bytes}',
            f'sflow enable {interface}',
            'interfaces enabled: 1',
        )

        for expected_entry in expected_entries:
            self.assertIn(expected_entry, out)

        self.cli_set(base_path + ['settings', 'interface', iface_2, 'driver', driver])
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

    def test_18_resource_limits(self):
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

    def test_19_vpp_pppoe_mapping(self):
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

        # Enable PPPoE control-plane integration with VPP
        self.cli_set(pppoe_base + ['interface', interface, 'vpp-cp'])
        self.cli_set(pppoe_base + ['interface', f'{interface}.{vni}', 'vpp-cp'])

        self.cli_commit()

        # Validate configuration values
        config = read_file(config_file)

        # Validate configuration
        self.assertIn(f'interface={interface},vpp-cp=true', config)
        self.assertIn(f'interface={interface}.{vni},vpp-cp=true', config)

        # Check pppoe mapping
        _, out = rc_cmd('sudo vppctl show pppoe control-plane binding')
        self.assertRegex(out, rf'{interface}\s+tap4096')
        self.assertRegex(out, rf'{interface}.{vni}\s+tap4096.23')

        # check if dependency is called and mapping is correct after changes in vpp script
        self.cli_set(
            base_path + ['settings', 'interface', interface, 'dpdk-options', 'promisc']
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

    def test_20_kernel_options_hugepages(self):
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

    def test_21_static_arp(self):
        host = '192.0.2.10'
        mac = '00:01:02:03:04:0a'
        path_static_arp = ['protocols', 'static', 'arp']

        self.cli_set(['interfaces', 'ethernet', interface, 'address', '192.0.2.1/24'])
        self.cli_set(
            path_static_arp + ['interface', interface, 'address', host, 'mac', mac]
        )
        self.cli_commit()

        # Change VPP configuration
        self.cli_set(base_path + ['settings', 'unix', 'poll-sleep-usec', '50'])

        # Ensure arp entry is not disappeared
        _, neighbors = rc_cmd('sudo ip neighbor')
        self.assertIn(f'{host} dev {interface} lladdr {mac}', neighbors)

        # Check VPP IP neighbors
        _, vpp_neighbors = rc_cmd('sudo vppctl show ip neighbors')
        self.assertRegex(vpp_neighbors, rf'{host}\s+S\s+{mac}\s+{interface}')

        self.cli_delete(path_static_arp)

    def test_22_1_vpp_ipfix(self):
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

    def test_22_2_vpp_ipfix_bond(self):
        base_ipfix = base_path + ['ipfix']
        base_bond = base_path + ['interfaces', 'bonding']
        iface_bond = 'bond0'
        collector_ip = '127.0.0.2'
        collector_src = '127.0.0.1'

        self.cli_set(base_bond + [iface_bond, 'kernel-interface', 'vpptun0'])
        self.cli_set(base_bond + [iface_bond, 'member', 'interface', iface_bond])

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


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
