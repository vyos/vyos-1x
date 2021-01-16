#!/usr/bin/env python3
#
# Copyright (C) 2020-2021 VyOS maintainers and contributors
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
from netifaces import interfaces

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import read_file
from vyos.validate import is_intf_addr_assigned
from vyos.ifconfig import Interface

class VRFTest(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        self._vrfs = ['red', 'green', 'blue']

    def tearDown(self):
        # delete all VRFs
        self.session.delete(['vrf'])
        self.session.commit()
        del self.session

    def test_vrf_table_id(self):
        table = 1000
        for vrf in self._vrfs:
            base = ['vrf', 'name', vrf]
            description = f'VyOS-VRF-{vrf}'
            self.session.set(base + ['description', description])

            if vrf == 'green':
                self.session.set(base + ['disable'])

            # check validate() - a table ID is mandatory
            with self.assertRaises(ConfigSessionError):
                self.session.commit()

            self.session.set(base + ['table', str(table)])
            table += 1

        # commit changes
        self.session.commit()

        # Verify VRF configuration
        for vrf in self._vrfs:
            description = f'VyOS-VRF-{vrf}'
            self.assertTrue(vrf in interfaces())
            vrf_if = Interface(vrf)
            # validate proper interface description
            self.assertEqual(vrf_if.get_alias(), description)
            # validate admin up/down state of VRF
            state = 'up'
            if vrf == 'green':
                state = 'down'
            self.assertEqual(vrf_if.get_admin_state(), state)

    def test_vrf_loopback_ips(self):
        table = 1000
        for vrf in self._vrfs:
            base = ['vrf', 'name', vrf]
            self.session.set(base + ['table', str(table)])
            table += 1

        # commit changes
        self.session.commit()

        # Verify VRF configuration
        for vrf in self._vrfs:
            self.assertTrue(vrf in interfaces())
            self.assertTrue(is_intf_addr_assigned(vrf, '127.0.0.1'))
            self.assertTrue(is_intf_addr_assigned(vrf, '::1'))

    def test_vrf_table_id_is_unalterable(self):
        # Linux Kernel prohibits the change of a VRF table  on the fly.
        # VRF must be deleted and recreated!
        table = 666
        vrf = self._vrfs[0]
        base = ['vrf', 'name', vrf]
        self.session.set(base + ['table', str(table)])

        # commit changes
        self.session.commit()

        # Check if VRF has been created
        self.assertTrue(vrf in interfaces())

        table += 1
        self.session.set(base + ['table', str(table)])
        # check validate() - table ID can not be altered!
        with self.assertRaises(ConfigSessionError):
            self.session.commit()


if __name__ == '__main__':
    unittest.main(verbosity=2)
