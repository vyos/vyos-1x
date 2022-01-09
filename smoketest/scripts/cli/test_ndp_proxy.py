#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.util import cmd

base_path = ['service', 'ndp-proxy']

class TaskNdpProxy(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_ndp_proxy(self):
        self.cli_set(base_path + ['interface', 'eth0', 'ttl', '30000'])
        self.cli_set(base_path + ['interface', 'eth0', 'timeout', '500'])
        self.cli_set(base_path + ['interface', 'eth0', 'prefix', 'fc00::/64', 'mode', 'auto'])
        self.cli_commit()

        self.cli_set(base_path + ['interface', 'eth0', 'prefix', 'fc00::/64', 'mode', 'static'])
        self.cli_commit()

        self.cli_set(base_path + ['interface', 'eth0', 'prefix', 'fc00::/64', 'mode', 'iface'])
        self.cli_set(base_path + ['interface', 'eth0', 'prefix', 'fc00::/64', 'iface', 'eth0'])
        self.cli_commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
