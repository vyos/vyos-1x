#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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

from vyos.component_version import legacy_from_system, from_system

# After T3474, component versions should be updated in the files in
# vyos-1x/interface-definitions/include/version/
# This test verifies that the legacy version in curver_DATA does not exceed
# that in the xml cache.
class TestComponentVersion(unittest.TestCase):
    def setUp(self):
        self.legacy_d = legacy_from_system()
        self.xml_d = from_system()

    def test_component_version(self):
        self.assertTrue(set(self.legacy_d).issubset(set(self.xml_d)))
        for k, v in self.legacy_d.items():
            self.assertTrue(v <= self.xml_d[k])

if __name__ == '__main__':
    unittest.main(verbosity=2)
