#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
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

from base_accel_ppp_test import BasicAccelPPPTest

class TestVPNPPTPServer(BasicAccelPPPTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['vpn', 'pptp', 'remote-access']
        cls._config_file = '/run/accel-pppd/pptp.conf'
        cls._chap_secrets = '/run/accel-pppd/pptp.chap-secrets'
        cls._protocol_section = 'pptp'
        # call base-classes classmethod
        super(TestVPNPPTPServer, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(TestVPNPPTPServer, cls).tearDownClass()

    def basic_protocol_specific_config(self):
        pass

if __name__ == '__main__':
    unittest.main(verbosity=2)
