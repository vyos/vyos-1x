#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.ifconfig.vrrp import VRRP
from vyos.util import cmd
from vyos.util import process_named_running
from vyos.util import read_file
from vyos.template import inc_ip

PROCESS_NAME = 'keepalived'
KEEPALIVED_CONF = VRRP.location['config']
base_path = ['high-availability', 'vrrp']

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

        self.cli_delete(base_path)
        self.cli_commit()

        # Process must be terminated after deleting the config
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_01_default_values(self):
        for group in groups:
            vlan_id = group.lstrip('VLAN')
            vip = f'100.64.{vlan_id}.1/24'
            group_base = base_path + ['group', group]

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
            self.assertIn(f'    {vip}', config)

    def test_02_simple_options(self):
        advertise_interval = '77'
        priority = '123'
        preempt_delay = '400'

        for group in groups:
            vlan_id = group.lstrip('VLAN')
            vip = f'100.64.{vlan_id}.1/24'
            group_base = base_path + ['group', group]

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
            self.cli_set(group_base + ['authentication', 'password', f'vyos-{group}'])

        # commit changes
        self.cli_commit()

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
            self.assertIn(f'auth_pass "vyos-{group}"', config)
            self.assertIn(f'auth_type PASS', config)

    def test_03_sync_group(self):
        sync_group = 'VyOS'

        for group in groups:
            vlan_id = group.lstrip('VLAN')
            vip = f'100.64.{vlan_id}.1/24'
            group_base = base_path + ['group', group]

            self.cli_set(['interfaces', 'ethernet', vrrp_interface, 'vif', vlan_id, 'address', inc_ip(vip, 1) + '/' + vip.split('/')[-1]])

            self.cli_set(group_base + ['interface', f'{vrrp_interface}.{vlan_id}'])
            self.cli_set(group_base + ['address', vip])
            self.cli_set(group_base + ['vrid', vlan_id])

            self.cli_set(base_path + ['sync-group', sync_group, 'member', group])

        # commit changes
        self.cli_commit()

        for group in groups:
            vlan_id = group.lstrip('VLAN')
            vip = f'100.64.{vlan_id}.1/24'
            config = getConfig(f'vrrp_instance {group}')

            self.assertIn(f'interface {vrrp_interface}.{vlan_id}', config)
            self.assertIn(f'virtual_router_id {vlan_id}', config)
            self.assertIn(f'    {vip}', config)

        config = getConfig(f'vrrp_sync_group {sync_group}')
        self.assertIn(r'group {', config)
        for group in groups:
            self.assertIn(f'{group}', config)

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
