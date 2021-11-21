#!/usr/bin/env python3
#
# Copyright (C) 2020-2021 VyOS maintainers and contributors
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

from vyos.configsession import ConfigSessionError

base_path = ['system', 'acceleration', 'qat']

class TestIntelQAT(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_simple_unsupported(self):
        # Check if configuration script is in place and that the config script
        # throws an error as QAT device is not present in Qemu. This *must* be
        # extended with QAT autodetection once run on a QAT enabled device

        # configure some system display
        self.cli_set(base_path)

        # An error must be thrown if QAT device could not be found
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
