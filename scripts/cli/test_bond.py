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

import os
import unittest
import vyos.config
import vyos.configsession

from netifaces import ifaddresses, AF_INET, AF_INET6
from vyos.validate import is_intf_addr_assigned

base_path = ['interfaces', 'bonding']
test_addr = ['192.0.2.1/25', '2001:db8:1::ffff/64']
interfaces = ['bond0']

class TestInterfacesBond(unittest.TestCase):
    def setUp(self):
        self.session = vyos.configsession.ConfigSession(os.getpid())
        env = self.session.get_session_env()
        self.config = vyos.config.Config(session_env=env)

    def tearDown(self):
        # Delete existing interfaces
        self.session.delete(base_path)
        self.session.commit()

    def test_add_address(self):
        """ Check if address is added to interface """
        for intf in interfaces:
            for addr in test_addr:
                self.session.set(base_path + [intf, 'address', addr])
        self.session.commit()

        for intf in interfaces:
            for af in AF_INET, AF_INET6:
                for addr in ifaddresses(intf)[af]:
                    self.assertTrue(is_intf_addr_assigned(intf, addr['addr']))

if __name__ == '__main__':
    unittest.main()
