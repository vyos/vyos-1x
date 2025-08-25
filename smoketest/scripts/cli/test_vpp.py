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
import sys
import unittest
from collections import defaultdict

from json import loads

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file
from vyos.utils.process import rc_cmd
from vyos.utils.system import sysctl_read
from vyos.vpp.utils import human_page_memory_to_bytes

sys.path.append(os.getenv('vyos_completion_dir'))
from list_mem_page_size import list_mem_page_size

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

    def test_01_vpp_basic(self):
        main_core = '0'
        poll_sleep = '0'

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

    @unittest.skip('Skipping temporary bonding, sometimes get recursion T7117')
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
        self.cli_set(base_interface_path + ['xdp-options', 'no-syscall-lock'])

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
        sizes = ['default', 'default-hugepage'] + list_mem_page_size()
        for size in sizes:
            if human_page_memory_to_bytes(size) >= 1 << 30:
                continue
            self.cli_set(base_path + ['settings', 'buffers', 'page-size', size])
            self.cli_commit()

            conf = get_vpp_config()
            self.assertEqual(conf['buffers']['page-size'], size)

    def test_13_2_statseg_page_size(self):
        sizes = ['default', 'default-hugepage'] + list_mem_page_size()
        for size in sizes:
            if human_page_memory_to_bytes(size) >= 1 << 30:
                continue
            self.cli_set(base_path + ['settings', 'statseg', 'page-size', size])
            self.cli_commit()

            conf = get_vpp_config()
            self.assertEqual(conf['statseg']['page-size'], size)

    def test_13_3_mem_page_size(self):
        sizes = ['default', 'default-hugepage'] + list_mem_page_size()
        for size in sizes:
            if human_page_memory_to_bytes(size) >= 1 << 30:
                continue
            self.cli_set(
                base_path + ['settings', 'memory', 'main-heap-page-size', size]
            )
            self.cli_commit()

            conf = get_vpp_config()
            self.assertEqual(conf['memory']['main-heap-page-size'], size)

    def test_14_mem_default_hugepage(self):
        sizes = list_mem_page_size(hugepage_only=True)
        for size in sizes:
            if human_page_memory_to_bytes(size) >= 1 << 30:
                continue
            self.cli_set(
                base_path + ['settings', 'memory', 'default-hugepage-size', size]
            )
            self.cli_commit()

            conf = get_vpp_config()
            self.assertEqual(conf['memory']['default-hugepage-size'], size)

    def test_15_vpp_ipsec_xfrm_nl(self):
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

    def test_16_vpp_cgnat(self):
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

    def test_17_vpp_nat(self):
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
        self.cli_set(
            base_nat + ['exclude', 'rule', '100', 'local-address', exclude_local_addr]
        )
        self.cli_set(
            base_nat + ['exclude', 'rule', '100', 'local-port', exclude_local_port]
        )
        self.cli_set(
            base_nat + ['static', 'rule', '100', 'external', 'address', static_ext_addr]
        )
        self.cli_set(
            base_nat + ['static', 'rule', '100', 'local', 'address', static_local_addr]
        )

        self.cli_set(base_nat_settings + ['no-forwarding'])
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

    def test_18_vpp_sflow(self):
        base_sflow = ['system', 'sflow']

        self.cli_set(base_path + ['sflow', 'interface', interface])
        self.cli_set(base_sflow + ['interface', interface])
        self.cli_set(base_sflow + ['server', '127.0.0.1'])
        self.cli_set(base_sflow + ['vpp'])
        self.cli_commit()

        # Check sFlow
        _, out = rc_cmd('sudo vppctl show sflow')

        expected_entries = (
            'sflow sampling-direction ingress',
            f'sflow enable {interface}',
            'interfaces enabled: 1',
        )

        for expected_entry in expected_entries:
            self.assertIn(expected_entry, out)

        self.cli_delete(base_sflow)
        self.cli_commit()

    def test_19_resource_limits(self):
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
