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

from psutil import process_iter
from vyos.configsession import ConfigSession, ConfigSessionError
from vyos.util import read_file

config_file = '/etc/ppp/peers/{}'
base_path = ['interfaces', 'pppoe']

def get_config_value(interface, key):
    with open(config_file.format(interface), 'r') as f:
        for line in f:
            if line.startswith(key):
                return list(line.split())
    return []

class PPPoEInterfaceTest(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        self._interfaces = ['pppoe0', 'pppoe1', 'pppoe2']

    def tearDown(self):
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_pppoe_1(self):
        """ Check if PPPoE dialer can be configured and runs """
        # ensure source-interface is available
        source_interface = 'eth0'
        self.session.set(['interfaces', 'ethernet', source_interface])

        for interface in self._interfaces:
            user = 'VyOS-user-' + interface
            passwd = 'VyOS-passwd-' + interface

            self.session.set(base_path + [interface, 'authentication', 'user', user])
            self.session.set(base_path + [interface, 'authentication', 'password', passwd])
            self.session.set(base_path + [interface, 'default-route', 'auto'])
            self.session.set(base_path + [interface, 'mtu', '1400'])
            self.session.set(base_path + [interface, 'no-peer-dns'])

            # check validate() - a source-interface is required
            with self.assertRaises(ConfigSessionError):
                self.session.commit()
            self.session.set(base_path + [interface, 'source-interface', 'eth0'])

            # commit changes
            self.session.commit()

        # verify configuration file(s)
        for interface in self._interfaces:
            user = 'VyOS-user-' + interface
            password = 'VyOS-passwd-' + interface

            cur_mtu = get_config_value(interface, 'mtu')[1]
            cur_user = get_config_value(interface, 'user')[1].replace('"', '')
            cur_password = get_config_value(interface, 'password')[1].replace('"', '')
            cur_default_route = get_config_value(interface, 'defaultroute')[0]
            cur_ifname = get_config_value(interface, 'ifname')[1]

            self.assertTrue(cur_mtu == '1400')
            self.assertTrue(cur_user == user)
            self.assertTrue(cur_password == password)
            self.assertTrue(cur_default_route == 'defaultroute')
            self.assertTrue(cur_ifname == interface)

            # Check if ppp process is running in the interface in question
            running = False
            for p in process_iter():
                if "pppd" in p.name():
                    if interface in p.cmdline():
                        running = True

            self.assertTrue(running)

if __name__ == '__main__':
    unittest.main()
