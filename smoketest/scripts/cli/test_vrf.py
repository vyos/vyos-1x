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

from vyos.configsession import ConfigSession, ConfigSessionError
from vyos.util import read_file
from vyos.validate import is_intf_addr_assigned

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
            description = "VyOS-VRF-" + vrf
            self.session.set(base + ['description', description])

            # check validate() - a table ID is mandatory
            with self.assertRaises(ConfigSessionError):
                self.session.commit()

            self.session.set(base + ['table', str(table)])
            table += 1

        # commit changes
        self.session.commit()

    def test_vrf_loopback_ips(self):
        table = 1000
        for vrf in self._vrfs:
            base = ['vrf', 'name', vrf]
            self.session.set(base + ['table', str(table)])
            table += 1

        # commit changes
        self.session.commit()
        for vrf in self._vrfs:
            self.assertTrue(is_intf_addr_assigned(vrf, '127.0.0.1'))
            self.assertTrue(is_intf_addr_assigned(vrf, '::1'))

if __name__ == '__main__':
    unittest.main(verbosity=2)
