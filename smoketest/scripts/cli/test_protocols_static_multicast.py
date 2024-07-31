#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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

from base_vyostest_shim import VyOSUnitTestSHIM


base_path = ['protocols', 'static', 'multicast']


class TestProtocolsStaticMulticast(VyOSUnitTestSHIM.TestCase):

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        mroute = self.getFRRconfig('ip mroute', end='')
        self.assertFalse(mroute)

    def test_01_static_multicast(self):

        self.cli_set(base_path + ['route', '224.202.0.0/24', 'next-hop', '224.203.0.1'])
        self.cli_set(base_path + ['interface-route', '224.203.0.0/24', 'next-hop-interface', 'eth0'])

        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = self.getFRRconfig('ip mroute', end='')

        self.assertIn('ip mroute 224.202.0.0/24 224.203.0.1', frrconfig)
        self.assertIn('ip mroute 224.203.0.0/24 eth0', frrconfig)


if __name__ == '__main__':
    unittest.main(verbosity=2)
