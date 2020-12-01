#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import cmd
from vyos.util import process_named_running
from vyos.util import read_file
from vyos.template import inc_ip
from vyos.template import address_from_cidr
from vyos.template import netmask_from_cidr

PROCESS_NAME = 'dhcpd'
DHCPD_CONF = '/run/dhcp-server/dhcpd.conf'
base_path = ['service', 'dhcp-server']
subnet = '192.0.2.0/25'
router = inc_ip(subnet, 1)

class TestServiceDHCPServer(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        cidr_mask = subnet.split('/')[-1]
        self.session.set(['interfaces', 'dummy', 'dum8765', 'address', f'{router}/{cidr_mask}'])

    def tearDown(self):
        self.session.delete(['interfaces', 'dummy', 'dum8765'])
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_single_pool(self):
        shared_net_name = 'SMOKE-1'

        dns_1 = inc_ip(subnet, 2)
        dns_2 = inc_ip(subnet, 3)
        domain_name = 'vyos.net'
        range_0_start = inc_ip(subnet, 10)
        range_0_stop  = inc_ip(subnet, 20)
        range_1_start = inc_ip(subnet, 40)
        range_1_stop  = inc_ip(subnet, 50)

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]
        # we use the first subnet IP address as default gateway
        self.session.set(pool + ['default-router', router])
        self.session.set(pool + ['dns-server', dns_1])
        self.session.set(pool + ['dns-server', dns_2])
        self.session.set(pool + ['domain-name', domain_name])

        # check validate() - No DHCP address range or active static-mapping set
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(pool + ['range', '0', 'start', range_0_start])
        self.session.set(pool + ['range', '0', 'stop', range_0_stop])
        self.session.set(pool + ['range', '1', 'start', range_1_start])
        self.session.set(pool + ['range', '1', 'stop', range_1_stop])

        # commit changes
        self.session.commit()

        config = read_file(DHCPD_CONF)
        network = address_from_cidr(subnet)
        netmask = netmask_from_cidr(subnet)
        self.assertIn(f'ddns-update-style none;', config)
        self.assertIn(f'subnet {network} netmask {netmask}' + r' {', config)
        self.assertIn(f'option domain-name-servers {dns_1}, {dns_2};', config)
        self.assertIn(f'option routers {router};', config)
        self.assertIn(f'option domain-name "{domain_name}";', config)
        self.assertIn(f'default-lease-time 86400;', config)
        self.assertIn(f'max-lease-time 86400;', config)
        self.assertIn(f'range {range_0_start} {range_0_stop};', config)
        self.assertIn(f'range {range_1_start} {range_1_stop};', config)
        self.assertIn(f'set shared-networkname = "{shared_net_name}";', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    unittest.main()
