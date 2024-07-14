#!/usr/bin/env python3
# Copyright 2024 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.


import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError


class TestConfigDep(VyOSUnitTestSHIM.TestCase):
    def test_configdep_error(self):
        address_group = 'AG'
        address = '192.168.137.5'
        nat_base = ['nat', 'source', 'rule', '10']
        interface = 'eth1'

        self.cli_set(['firewall', 'group', 'address-group', address_group,
                      'address', address])
        self.cli_set(nat_base + ['outbound-interface', 'name', interface])
        self.cli_set(nat_base + ['source', 'group', 'address-group', address_group])
        self.cli_set(nat_base + ['translation', 'address', 'masquerade'])
        self.cli_commit()

        self.cli_delete(['firewall'])
        # check error in call to dependent script (nat)
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # clean up remaining
        self.cli_delete(['nat'])
        self.cli_commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
