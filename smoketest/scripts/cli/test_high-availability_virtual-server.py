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

from vyos.ifconfig.vrrp import VRRP
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file

PROCESS_NAME = 'keepalived'
KEEPALIVED_CONF = VRRP.location['config']
base_path = ['high-availability']
vrrp_interface = 'eth1'

class TestHAVirtualServer(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        self.cli_delete(['interfaces', 'ethernet', vrrp_interface, 'address'])
        self.cli_delete(base_path)
        self.cli_commit()

        # Process must be terminated after deleting the config
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_01_ha_virtual_server(self):
        algo = 'least-connection'
        delay = '10'
        method = 'nat'
        persistence_timeout = '600'
        vs = 'serv-one'
        vip = '203.0.113.111'
        vport = '2222'
        rservers = ['192.0.2.21', '192.0.2.22', '192.0.2.23']
        rport = '22'
        proto = 'tcp'
        connection_timeout = '30'

        vserver_base = base_path + ['virtual-server']

        self.cli_set(vserver_base + [vs, 'address', vip])
        self.cli_set(vserver_base + [vs, 'algorithm', algo])
        self.cli_set(vserver_base + [vs, 'delay-loop', delay])
        self.cli_set(vserver_base + [vs, 'forward-method', method])
        self.cli_set(vserver_base + [vs, 'persistence-timeout', persistence_timeout])
        self.cli_set(vserver_base + [vs, 'port', vport])
        self.cli_set(vserver_base + [vs, 'protocol', proto])
        for rs in rservers:
            self.cli_set(vserver_base + [vs, 'real-server', rs, 'connection-timeout', connection_timeout])
            self.cli_set(vserver_base + [vs, 'real-server', rs, 'port', rport])

        # commit changes
        self.cli_commit()

        config = read_file(KEEPALIVED_CONF)

        self.assertIn(f'virtual_server {vip} {vport}', config)
        self.assertIn(f'delay_loop {delay}', config)
        self.assertIn(f'lb_algo lc', config)
        self.assertIn(f'lb_kind {method.upper()}', config)
        self.assertIn(f'persistence_timeout {persistence_timeout}', config)
        self.assertIn(f'protocol {proto.upper()}', config)
        for rs in rservers:
            self.assertIn(f'real_server {rs} {rport}', config)
            self.assertIn(f'{proto.upper()}_CHECK', config)
            self.assertIn(f'connect_timeout {connection_timeout}', config)

    def test_02_ha_virtual_server_and_vrrp(self):
        algo = 'least-connection'
        delay = '15'
        method = 'nat'
        persistence_timeout = '300'
        vs = 'serv-two'
        vip = '203.0.113.222'
        vport = '22322'
        rservers = ['192.0.2.11', '192.0.2.12']
        rport = '222'
        proto = 'tcp'
        connection_timeout = '23'
        group = 'VyOS'
        vrid = '99'

        vrrp_base = base_path + ['vrrp', 'group']
        vserver_base = base_path + ['virtual-server']

        self.cli_set(['interfaces', 'ethernet', vrrp_interface, 'address', '203.0.113.10/24'])

        # VRRP config
        self.cli_set(vrrp_base + [group, 'description', group])
        self.cli_set(vrrp_base + [group, 'interface', vrrp_interface])
        self.cli_set(vrrp_base + [group, 'address', vip + '/24'])
        self.cli_set(vrrp_base + [group, 'vrid', vrid])

        # Virtual-server config
        self.cli_set(vserver_base + [vs, 'address', vip])
        self.cli_set(vserver_base + [vs, 'algorithm', algo])
        self.cli_set(vserver_base + [vs, 'delay-loop', delay])
        self.cli_set(vserver_base + [vs, 'forward-method', method])
        self.cli_set(vserver_base + [vs, 'persistence-timeout', persistence_timeout])
        self.cli_set(vserver_base + [vs, 'port', vport])
        self.cli_set(vserver_base + [vs, 'protocol', proto])
        for rs in rservers:
            self.cli_set(vserver_base + [vs, 'real-server', rs, 'connection-timeout', connection_timeout])
            self.cli_set(vserver_base + [vs, 'real-server', rs, 'port', rport])

        # commit changes
        self.cli_commit()

        config = read_file(KEEPALIVED_CONF)

        # Keepalived vrrp
        self.assertIn(f'# {group}', config)
        self.assertIn(f'interface {vrrp_interface}', config)
        self.assertIn(f'virtual_router_id {vrid}', config)
        self.assertIn(f'priority 100', config) # default value
        self.assertIn(f'advert_int 1', config) # default value
        self.assertIn(f'preempt_delay 0', config) # default value

        # Keepalived virtual-server
        self.assertIn(f'virtual_server {vip} {vport}', config)
        self.assertIn(f'delay_loop {delay}', config)
        self.assertIn(f'lb_algo lc', config)
        self.assertIn(f'lb_kind {method.upper()}', config)
        self.assertIn(f'persistence_timeout {persistence_timeout}', config)
        self.assertIn(f'protocol {proto.upper()}', config)
        for rs in rservers:
            self.assertIn(f'real_server {rs} {rport}', config)
            self.assertIn(f'{proto.upper()}_CHECK', config)
            self.assertIn(f'connect_timeout {connection_timeout}', config)


if __name__ == '__main__':
    unittest.main(verbosity=2)
