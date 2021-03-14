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

import unittest

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import get_interface_config

from base_interfaces_test import BasicInterfaceTest

mtu = 1500

class ERSPanTunnelInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
        super().setUp()

        self._base_path = ['interfaces', 'erspan']
        self._test_mtu = True

        self.local_v4 = '10.1.1.1'
        self.local_v6 = '2001:db8::1'
        self.remote_v4 = '10.2.2.2'
        self.remote_v6 = '2001:db9::1'

    def tearDown(self):
        self.session.delete(['interfaces', 'erspan'])
        super().tearDown()

    def test_erspan_ipv4(self):
        interface = 'ersp100'
        encapsulation = 'erspan'
        key = 123

        self.session.set(self._base_path + [interface, 'encapsulation', encapsulation])
        self.session.set(self._base_path + [interface, 'source-address', self.local_v4])
        self.session.set(self._base_path + [interface, 'remote', self.remote_v4])
        self.session.set(self._base_path + [interface, 'parameters', 'ip' , 'key', str(key)])

        self.session.commit()

        conf = get_interface_config(interface)
        self.assertEqual(interface, conf['ifname'])
        self.assertEqual(encapsulation, conf['linkinfo']['info_kind'])
        self.assertEqual(mtu, conf['mtu'])

        self.assertEqual(self.local_v4,  conf['linkinfo']['info_data']['local'])
        self.assertEqual(self.remote_v4, conf['linkinfo']['info_data']['remote'])


    def test_erspan_ipv6(self):
        interface = 'ersp1000'
        encapsulation = 'ip6erspan'
        key = 123

        self.session.set(self._base_path + [interface, 'encapsulation', encapsulation])
        self.session.set(self._base_path + [interface, 'source-address', self.local_v6])
        self.session.set(self._base_path + [interface, 'remote', self.remote_v6])
        self.session.set(self._base_path + [interface, 'parameters', 'ip' , 'key', str(key)])

        self.session.commit()

        conf = get_interface_config(interface)
        self.assertEqual(interface, conf['ifname'])
        self.assertEqual(encapsulation, conf['linkinfo']['info_kind'])
        self.assertEqual(mtu, conf['mtu'])

        self.assertEqual(self.local_v6,  conf['linkinfo']['info_data']['local'])
        self.assertEqual(self.remote_v6, conf['linkinfo']['info_data']['remote'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
