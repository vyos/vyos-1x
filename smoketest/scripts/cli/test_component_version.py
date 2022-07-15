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

from vyos.systemversions import get_system_versions, get_system_component_version

# After T3474, component versions should be updated in the files in
# vyos-1x/interface-definitions/include/version/
# This test verifies that the legacy version in curver_DATA does not exceed
# that in the xml cache.
class TestComponentVersion(unittest.TestCase):
    def setUp(self):
        self.legacy_d = get_system_versions()
        self.xml_d = get_system_component_version()
        self.set_legacy_d = set(self.legacy_d)
        self.set_xml_d = set(self.xml_d)

    def test_component_version(self):
        bool_issubset = (self.set_legacy_d.issubset(self.set_xml_d))
        if not bool_issubset:
            missing = self.set_legacy_d.difference(self.set_xml_d)
            print(f'\n\ncomponents in legacy but not in XML: {missing}')
            print('new components must be listed in xml-component-version.xml.in')
        self.assertTrue(bool_issubset)

        bad_component_version = False
        for k, v in self.legacy_d.items():
            bool_inequality = (v <= self.xml_d[k])
            if not bool_inequality:
                print(f'\n\n{k} has not been updated in XML component versions:')
                print(f'legacy version {v}; XML version {self.xml_d[k]}')
                bad_component_version = True
        self.assertFalse(bad_component_version)

if __name__ == '__main__':
    unittest.main(verbosity=2)
