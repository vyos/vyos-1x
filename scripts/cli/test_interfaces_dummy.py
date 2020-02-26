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

from base_interfaces_test import BasicInterfaceTest

class DummyInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
         super().setUp()
         self._base_path = ['interfaces', 'dummy']
         self._interfaces = ['dum0', 'dum1', 'dum2']

if __name__ == '__main__':
    unittest.main()
