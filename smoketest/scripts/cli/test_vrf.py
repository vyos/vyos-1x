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

import re
import os
import unittest
from netifaces import interfaces

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import read_file
from vyos.validate import is_intf_addr_assigned
from vyos.ifconfig import Interface

base_path = ['vrf']
vrfs = ['red', 'green', 'blue', 'foo-bar', 'baz_foo']

class VRFTest(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())

    def tearDown(self):
        # delete all VRFs
        self.session.delete(base_path)
        self.session.commit()
        for vrf in vrfs:
            self.assertTrue(vrf not in interfaces())

    def test_vrf_table_id(self):
        table = '1000'
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            description = f'VyOS-VRF-{vrf}'
            self.session.set(base + ['description', description])

            # check validate() - a table ID is mandatory
            with self.assertRaises(ConfigSessionError):
                self.session.commit()

            self.session.set(base + ['table', table])
            if vrf == 'green':
                self.session.set(base + ['disable'])

            table = str(int(table) + 1)

        # commit changes
        self.session.commit()

        # Verify VRF configuration
        table = '1000'
        iproute2_config = read_file('/etc/iproute2/rt_tables.d/vyos-vrf.conf')
        for vrf in vrfs:
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

            # Test the iproute2 lookup file, syntax is as follows:
            #
            # # id       vrf name         comment
            # 1000       red              # VyOS-VRF-red
            # 1001       green            # VyOS-VRF-green
            #  ...
            regex = f'{table}\s+{vrf}\s+#\s+{description}'
            self.assertTrue(re.findall(regex, iproute2_config))
            table = str(int(table) + 1)

    def test_vrf_loopback_ips(self):
        table = '2000'
        for vrf in vrfs:
            base = base_path + ['name', vrf]
            self.session.set(base + ['table', str(table)])
            table = str(int(table) + 1)

        # commit changes
        self.session.commit()

        # Verify VRF configuration
        for vrf in vrfs:
            self.assertTrue(vrf in interfaces())
            self.assertTrue(is_intf_addr_assigned(vrf, '127.0.0.1'))
            self.assertTrue(is_intf_addr_assigned(vrf, '::1'))

    def test_vrf_table_id_is_unalterable(self):
        # Linux Kernel prohibits the change of a VRF table  on the fly.
        # VRF must be deleted and recreated!
        table = '1000'
        vrf = vrfs[0]
        base = base_path + ['name', vrf]
        self.session.set(base + ['table', table])

        # commit changes
        self.session.commit()

        # Check if VRF has been created
        self.assertTrue(vrf in interfaces())

        table = str(int(table) + 1)
        self.session.set(base + ['table', table])
        # check validate() - table ID can not be altered!
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
