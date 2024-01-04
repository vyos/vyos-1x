#!/usr/bin/env python3
#
# Copyright (C) 2019-2024 VyOS maintainers and contributors
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
from vyos.utils.process import cmd

modules = {
    "intel": ["e1000", "e1000e", "igb", "ixgbe", "ixgbevf", "i40e",
              "i40evf", "iavf"],
    "intel_qat": ["qat_200xx", "qat_200xxvf", "qat_c3xxx", "qat_c3xxxvf",
                  "qat_c62x", "qat_c62xvf", "qat_d15xx", "qat_d15xxvf",
                  "qat_dh895xcc", "qat_dh895xccvf"],
    "accel_ppp": ["ipoe", "vlan_mon"],
    "openvpn": ["ovpn-dco-v2"]
}

class TestKernelModules(unittest.TestCase):
    def test_load_modules(self):
        success = True
        not_found = []
        for msk in modules:
            not_found = []
            ms = modules[msk]
            for m in ms:
                # We want to uncover all modules that fail,
                # not fail at the first one
                try:
                    cmd(f'modprobe {m}')
                except:
                    success = False
                    not_found.append(m)

            self.assertTrue(success, 'One or more modules not found: ' + ', '.join(not_found))

if __name__ == '__main__':
    unittest.main(verbosity=2)
