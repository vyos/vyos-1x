#!/usr/bin/env python3
#
# Copyright (C) 2021-2022 VyOS maintainers and contributors
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

from vyos.util import cmd

class TestZonePolicy(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(cls, cls).setUpClass()
        cls.cli_set(cls, ['firewall', 'name', 'smoketest', 'default-action', 'drop'])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['firewall'])
        super(cls, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(['zone-policy'])
        self.cli_commit()

    def test_basic_zone(self):
        self.cli_set(['zone-policy', 'zone', 'smoketest-eth0', 'interface', 'eth0'])
        self.cli_set(['zone-policy', 'zone', 'smoketest-eth0', 'from', 'smoketest-local', 'firewall', 'name', 'smoketest'])
        self.cli_set(['zone-policy', 'zone', 'smoketest-local', 'local-zone'])
        self.cli_set(['zone-policy', 'zone', 'smoketest-local', 'from', 'smoketest-eth0', 'firewall', 'name', 'smoketest'])

        self.cli_commit()

        nftables_search = [
            ['chain VZONE_smoketest-eth0'],
            ['chain VZONE_smoketest-local_IN'],
            ['chain VZONE_smoketest-local_OUT'],
            ['oifname { "eth0" }', 'jump VZONE_smoketest-eth0'],
            ['jump VZONE_smoketest-local_IN'],
            ['jump VZONE_smoketest-local_OUT'],
            ['iifname { "eth0" }', 'jump NAME_smoketest'],
            ['oifname { "eth0" }', 'jump NAME_smoketest']
        ]

        nftables_output = cmd('sudo nft list table ip filter')

        for search in nftables_search:
            matched = False
            for line in nftables_output.split("\n"):
                if all(item in line for item in search):
                    matched = True
                    break
            self.assertTrue(matched)


if __name__ == '__main__':
    unittest.main(verbosity=2)
