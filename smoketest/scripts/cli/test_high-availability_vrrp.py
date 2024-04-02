#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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
from vyos.ifconfig.vrrp import VRRP
from vyos.utils.process import cmd
from vyos.utils.process import process_named_running
from vyos.template import inc_ip

PROCESS_NAME = 'keepalived'
KEEPALIVED_CONF = VRRP.location['config']
base_path = ['high-availability']

vrrp_interface = 'eth1'
groups = ['VLAN77', 'VLAN78', 'VLAN201']

def getConfig(string, end='}'):
    command = f'cat {KEEPALIVED_CONF} | sed -n "/^{string}/,/^{end}/p"'
    out = cmd(command)
    return out

class TestVRRP(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        for group in groups:
            vlan_id = group.lstrip('VLAN')
            self.cli_delete(['interfaces', 'ethernet', vrrp_interface, 'vif', vlan_id])

        self.cli_delete(base_path)
        self.cli_commit()

        # Process must be terminated after deleting the config
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_01_default_values(self):
        for group in groups:
            vlan_id = group.lstrip('VLAN')
            vip = f'100.64.{vlan_id}.1/24'
            group_base = base_path + ['vrrp', 'group', group]

            self.cli_set(['interfaces', 'ethernet', vrrp_interface, 'vif', vlan_id, 'address', inc_ip(vip, 1) + '/' + vip.split('/')[-1]])

            self.cli_set(group_base + ['description', group])
            self.cli_set(group_base + ['interface', f'{vrrp_interface}.{vlan_id}'])
            self.cli_set(group_base + ['address', vip])
            self.cli_set(group_base + ['vrid', vlan_id])

        # commit changes
        self.cli_commit()

        for group in groups:
            vlan_id = group.lstrip('VLAN')
            vip = f'100.64.{vlan_id}.1/24'

            config = getConfig(f'vrrp_instance {group}')

            self.assertIn(f'# {group}', config)
            self.assertIn(f'interface {vrrp_interface}.{vlan_id}', config)
            self.assertIn(f'virtual_router_id {vlan_id}', config)
            self.assertIn(f'priority 100', config) # default value
            self.assertIn(f'advert_int 1', config) # default value
            self.assertIn(f'preempt_delay 0', config) # default value
            self.assertNotIn(f'use_vmac', config)
            self.assertIn(f'    {vip}', config)

    def test_02_simple_options(self):
        advertise_interval = '77'
        priority = '123'
        preempt_delay = '400'
        startup_delay = '120'
        garp_master_delay = '2'
        garp_master_repeat = '3'
        garp_master_refresh = '4'
        garp_master_refresh_repeat = '5'
        garp_interval = '1.5'
        group_garp_master_delay = '12'
        group_garp_master_repeat = '13'
        group_garp_master_refresh = '14'
        vrrp_version = '3'

        for group in groups:
            vlan_id = group.lstrip('VLAN')
            vip = f'100.64.{vlan_id}.1/24'
            group_base = base_path + ['vrrp', 'group', group]
            global_param_base = base_path + ['vrrp', 'global-parameters']

            self.cli_set(['interfaces', 'ethernet', vrrp_interface, 'vif', vlan_id, 'address', inc_ip(vip, 1) + '/' + vip.split('/')[-1]])

            self.cli_set(group_base + ['description', group])
            self.cli_set(group_base + ['interface', f'{vrrp_interface}.{vlan_id}'])
            self.cli_set(group_base + ['address', vip])
            self.cli_set(group_base + ['vrid', vlan_id])

            self.cli_set(group_base + ['advertise-interval', advertise_interval])
            self.cli_set(group_base + ['priority', priority])
            self.cli_set(group_base + ['preempt-delay', preempt_delay])

            self.cli_set(group_base + ['rfc3768-compatibility'])

            # Authentication
            self.cli_set(group_base + ['authentication', 'type', 'plaintext-password'])
            self.cli_set(group_base + ['authentication', 'password', f'{group}'])

            # GARP
            self.cli_set(group_base + ['garp', 'master-delay', group_garp_master_delay])
            self.cli_set(group_base + ['garp', 'master-repeat', group_garp_master_repeat])
            self.cli_set(group_base + ['garp', 'master-refresh', group_garp_master_refresh])

        # Global parameters
        #config = getConfig(f'global_defs')
        self.cli_set(global_param_base + ['startup-delay', f'{startup_delay}'])
        self.cli_set(global_param_base + ['garp', 'interval', f'{garp_interval}'])
        self.cli_set(global_param_base + ['garp', 'master-delay', f'{garp_master_delay}'])
        self.cli_set(global_param_base + ['garp', 'master-repeat', f'{garp_master_repeat}'])
        self.cli_set(global_param_base + ['garp', 'master-refresh', f'{garp_master_refresh}'])
        self.cli_set(global_param_base + ['garp', 'master-refresh-repeat', f'{garp_master_refresh_repeat}'])
        self.cli_set(global_param_base + ['version', vrrp_version])

        # commit changes
        self.cli_commit()

        # Check Global parameters
        config = getConfig(f'global_defs')
        self.assertIn(f'vrrp_startup_delay {startup_delay}', config)
        self.assertIn(f'vrrp_garp_interval {garp_interval}', config)
        self.assertIn(f'vrrp_garp_master_delay {garp_master_delay}', config)
        self.assertIn(f'vrrp_garp_master_repeat {garp_master_repeat}', config)
        self.assertIn(f'vrrp_garp_master_refresh {garp_master_refresh}', config)
        self.assertIn(f'vrrp_garp_master_refresh_repeat {garp_master_refresh_repeat}', config)
        self.assertIn(f'vrrp_version {vrrp_version}', config)

        for group in groups:
            vlan_id = group.lstrip('VLAN')
            vip = f'100.64.{vlan_id}.1/24'

            config = getConfig(f'vrrp_instance {group}')
            self.assertIn(f'# {group}', config)
            self.assertIn(f'state BACKUP', config)
            self.assertIn(f'interface {vrrp_interface}.{vlan_id}', config)
            self.assertIn(f'virtual_router_id {vlan_id}', config)
            self.assertIn(f'priority {priority}', config)
            self.assertIn(f'advert_int {advertise_interval}', config)
            self.assertIn(f'preempt_delay {preempt_delay}', config)
            self.assertIn(f'use_vmac {vrrp_interface}.{vlan_id}v{vlan_id}', config)
            self.assertIn(f'    {vip}', config)

            # Authentication
            self.assertIn(f'auth_pass "{group}"', config)
            self.assertIn(f'auth_type PASS', config)

            #GARP
            self.assertIn(f'garp_master_delay {group_garp_master_delay}', config)
            self.assertIn(f'garp_master_refresh {group_garp_master_refresh}', config)
            self.assertIn(f'garp_master_repeat {group_garp_master_repeat}', config)

    def test_03_sync_group(self):
        sync_group = 'VyOS'

        for group in groups:
            vlan_id = group.lstrip('VLAN')
            vip = f'100.64.{vlan_id}.1/24'
            group_base = base_path + ['vrrp', 'group', group]

            self.cli_set(['interfaces', 'ethernet', vrrp_interface, 'vif', vlan_id, 'address', inc_ip(vip, 1) + '/' + vip.split('/')[-1]])

            self.cli_set(group_base + ['interface', f'{vrrp_interface}.{vlan_id}'])
            self.cli_set(group_base + ['address', vip])
            self.cli_set(group_base + ['vrid', vlan_id])

            self.cli_set(base_path + ['vrrp', 'sync-group', sync_group, 'member', group])

        # commit changes
        self.cli_commit()

        for group in groups:
            vlan_id = group.lstrip('VLAN')
            vip = f'100.64.{vlan_id}.1/24'
            config = getConfig(f'vrrp_instance {group}')

            self.assertIn(f'interface {vrrp_interface}.{vlan_id}', config)
            self.assertIn(f'virtual_router_id {vlan_id}', config)
            self.assertNotIn(f'use_vmac', config)
            self.assertIn(f'    {vip}', config)

        config = getConfig(f'vrrp_sync_group {sync_group}')
        self.assertIn(r'group {', config)
        for group in groups:
            self.assertIn(f'{group}', config)

    def test_04_exclude_vrrp_interface(self):
        group = 'VyOS-WAN'
        none_vrrp_interface = 'eth2'
        vlan_id = '24'
        vip = '100.64.24.1/24'
        vip_dev = '192.0.2.2/24'
        vrid = '150'
        group_base = base_path + ['vrrp', 'group', group]

        self.cli_set(['interfaces', 'ethernet', vrrp_interface, 'vif', vlan_id, 'address', '100.64.24.11/24'])
        self.cli_set(group_base + ['interface', f'{vrrp_interface}.{vlan_id}'])
        self.cli_set(group_base + ['address', vip])
        self.cli_set(group_base + ['address', vip_dev, 'interface', none_vrrp_interface])
        self.cli_set(group_base + ['track', 'exclude-vrrp-interface'])
        self.cli_set(group_base + ['track', 'interface', none_vrrp_interface])
        self.cli_set(group_base + ['vrid', vrid])

        # commit changes
        self.cli_commit()

        config = getConfig(f'vrrp_instance {group}')

        self.assertIn(f'interface {vrrp_interface}.{vlan_id}', config)
        self.assertIn(f'virtual_router_id {vrid}', config)
        self.assertIn(f'dont_track_primary', config)
        self.assertIn(f'    {vip}', config)
        self.assertIn(f'    {vip_dev} dev {none_vrrp_interface}', config)
        self.assertIn(f'track_interface', config)
        self.assertIn(f'    {none_vrrp_interface}', config)

    def test_05_set_multiple_peer_address(self):
        group = 'VyOS-WAN'
        vlan_id = '24'
        vip = '100.64.24.1/24'
        peer_address_1 = '192.0.2.1'
        peer_address_2 = '192.0.2.2'
        vrid = '150'
        group_base = base_path + ['vrrp', 'group', group]

        self.cli_set(['interfaces', 'ethernet', vrrp_interface, 'vif', vlan_id, 'address', '100.64.24.11/24'])
        self.cli_set(group_base + ['interface', vrrp_interface])
        self.cli_set(group_base + ['address', vip])
        self.cli_set(group_base + ['peer-address', peer_address_1])
        self.cli_set(group_base + ['peer-address', peer_address_2])
        self.cli_set(group_base + ['vrid', vrid])

        # commit changes
        self.cli_commit()

        config = getConfig(f'vrrp_instance {group}')

        self.assertIn(f'interface {vrrp_interface}', config)
        self.assertIn(f'virtual_router_id {vrid}', config)
        self.assertIn(f'unicast_peer', config)
        self.assertIn(f'    {peer_address_1}', config)
        self.assertIn(f'    {peer_address_2}', config)

    def test_check_health_script(self):
        sync_group = 'VyOS'

        for group in groups:
            vlan_id = group.lstrip('VLAN')
            vip = f'100.64.{vlan_id}.1/24'
            group_base = base_path + ['vrrp', 'group', group]

            self.cli_set(['interfaces', 'ethernet', vrrp_interface, 'vif', vlan_id, 'address', inc_ip(vip, 1) + '/' + vip.split('/')[-1]])

            self.cli_set(group_base + ['interface', f'{vrrp_interface}.{vlan_id}'])
            self.cli_set(group_base + ['address', vip])
            self.cli_set(group_base + ['vrid', vlan_id])

            self.cli_set(group_base + ['health-check', 'ping', '127.0.0.1'])

        # commit changes
        self.cli_commit()

        for group in groups:
            config = getConfig(f'vrrp_instance {group}')
            self.assertIn(f'track_script', config)

        self.cli_set(base_path + ['vrrp', 'sync-group', sync_group, 'member', groups[0]])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(base_path + ['vrrp', 'group', groups[0], 'health-check'])
        self.cli_commit()

        for group in groups[1:]:
            config = getConfig(f'vrrp_instance {group}')
            self.assertIn(f'track_script', config)

        config = getConfig(f'vrrp_instance {groups[0]}')
        self.assertNotIn(f'track_script', config)

        config = getConfig(f'vrrp_sync_group {sync_group}')
        self.assertNotIn(f'track_script', config)

        self.cli_set(base_path + ['vrrp', 'sync-group', sync_group, 'health-check', 'ping', '127.0.0.1'])

        # commit changes
        self.cli_commit()

        config = getConfig(f'vrrp_instance {groups[0]}')
        self.assertNotIn(f'track_script', config)

        config = getConfig(f'vrrp_sync_group {sync_group}')
        self.assertIn(f'track_script', config)


if __name__ == '__main__':
    unittest.main(verbosity=2)
