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

import os
import platform
import unittest

kernel = platform.release()
with open(f'/boot/config-{kernel}') as f:
    config = f.read()

class TestKernelModules(unittest.TestCase):

    def test_radius_auth_t2886(self):
        # T2886 - RADIUS authentication - check for statically compiled
        # options (=y)
        for option in ['CONFIG_AUDIT', 'CONFIG_HAVE_ARCH_AUDITSYSCALL',
                       'CONFIG_AUDITSYSCALL', 'CONFIG_AUDIT_WATCH',
                       'CONFIG_AUDIT_TREE', 'CONFIG_AUDIT_ARCH']:
            self.asserIn(f'{option}=y', config)

if __name__ == '__main__':
    unittest.main()
