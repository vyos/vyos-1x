#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos.utils.cpu import cpu_arch
from vyos.utils.process import cmdl

modules = {
    "intel": ["e1000", "e1000e", "igb", "ixgbe", "ixgbevf", "i40e",
              "iavf", "ice"],
    "intel_qat": ["qat_200xx", "qat_200xxvf", "qat_c3xxx", "qat_c3xxxvf",
                  "qat_c62x", "qat_c62xvf", "qat_d15xx", "qat_d15xxvf",
                  "qat_dh895xcc", "qat_dh895xccvf"],
    "accel_ppp": ["ipoe", "vlan_mon"],
}

class TestKernelModules(unittest.TestCase):
    def _load_modules(self, name):
        not_found = []
        for module in modules[name]:
            # We want to uncover all modules that fail,
            # not fail at the first one
            try:
                cmdl(['modprobe', module])
            except:
                not_found.append(module)

        self.assertFalse(not_found, f'One or more {name} modules not found: '
                                    + ', '.join(not_found))

    @cpu_arch('amd64')
    def test_load_modules_intel(self):
        self._load_modules('intel')

    @cpu_arch('amd64')
    def test_load_modules_intel_qat(self):
        self._load_modules('intel_qat')

    def test_load_modules_accel_ppp(self):
        self._load_modules('accel_ppp')

if __name__ == '__main__':
    unittest.main(verbosity=2)
