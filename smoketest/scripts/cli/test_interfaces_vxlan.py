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

from vyos.configsession import ConfigSession, ConfigSessionError
from base_interfaces_test import BasicInterfaceTest

class VXLANInterfaceTest(BasicInterfaceTest.BaseTest):
    @classmethod
    def setUpClass(cls):
        cls._test_ip = True
        cls._test_ipv6 = True
        cls._test_mtu = True
        cls._base_path = ['interfaces', 'vxlan']
        cls._options = {
            'vxlan0': ['vni 10', 'remote 127.0.0.2'],
            'vxlan1': ['vni 20', 'group 239.1.1.1', 'source-interface eth0'],
        }
        cls._interfaces = list(cls._options)

if __name__ == '__main__':
    unittest.main(verbosity=2)
