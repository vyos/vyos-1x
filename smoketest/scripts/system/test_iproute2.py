#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

class TestIproute2(unittest.TestCase):
    def test_ip_is_symlink(self):
        # For an unknown reason VyOS 1.3.0-rc2 did not have a symlink from
        # /usr/sbin/ip -> /bin/ip - verify this now and forever
        real_file = '../bin/ip'
        symlink = '/usr/sbin/ip'
        self.assertTrue(os.path.islink(symlink))
        self.assertFalse(os.path.islink(real_file))
        self.assertEqual(os.readlink(symlink), real_file)

if __name__ == '__main__':
    unittest.main(verbosity=2)
