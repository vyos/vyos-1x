#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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

modules = {
    "intel": ["e1000", "e1000e", "igb", "ixgb", "ixgbe", "ixgbevf", "i40e", "i40evf"],
    "accel_ppp": ["ipoe", "vlan_mon"],
    "misc": ["wireguard"]
}

class TestKernelModules(unittest.TestCase):
    def test_load_modules(self):
        success = True
        for msk in modules:
            ms = modules[msk]
            for m in ms:
                # We want to uncover all modules that fail,
                # not fail at the first one
                try:
                    os.system("modprobe {0}".format(m))
                except:
                    success = False

            self.assertTrue(success)

if __name__ == '__main__':
    unittest.main()
