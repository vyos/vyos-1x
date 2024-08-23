#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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
from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.utils.file import read_file
from vyos.utils.process import is_systemd_service_active
from vyos.utils.system import sysctl_read

base_path = ['system', 'option']

class TestSystemOption(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_ctrl_alt_delete(self):
        self.cli_set(base_path + ['ctrl-alt-delete', 'reboot'])
        self.cli_commit()

        tmp = os.readlink('/lib/systemd/system/ctrl-alt-del.target')
        self.assertEqual(tmp, '/lib/systemd/system/reboot.target')

        self.cli_set(base_path + ['ctrl-alt-delete', 'poweroff'])
        self.cli_commit()

        tmp = os.readlink('/lib/systemd/system/ctrl-alt-del.target')
        self.assertEqual(tmp, '/lib/systemd/system/poweroff.target')

        self.cli_delete(base_path + ['ctrl-alt-delete', 'poweroff'])
        self.cli_commit()
        self.assertFalse(os.path.exists('/lib/systemd/system/ctrl-alt-del.target'))

    def test_reboot_on_panic(self):
        panic_file = '/proc/sys/kernel/panic'

        tmp = read_file(panic_file)
        self.assertEqual(tmp, '0')

        self.cli_set(base_path + ['reboot-on-panic'])
        self.cli_commit()

        tmp = read_file(panic_file)
        self.assertEqual(tmp, '60')

    def test_performance(self):
        tuned_service = 'tuned.service'

        self.assertFalse(is_systemd_service_active(tuned_service))

        # T3204 sysctl options must not be overwritten by tuned
        gc_thresh1 = '131072'
        gc_thresh2 = '262000'
        gc_thresh3 = '524000'

        self.cli_set(['system', 'sysctl', 'parameter', 'net.ipv4.neigh.default.gc_thresh1', 'value', gc_thresh1])
        self.cli_set(['system', 'sysctl', 'parameter', 'net.ipv4.neigh.default.gc_thresh2', 'value', gc_thresh2])
        self.cli_set(['system', 'sysctl', 'parameter', 'net.ipv4.neigh.default.gc_thresh3', 'value', gc_thresh3])

        self.cli_set(base_path + ['performance', 'throughput'])
        self.cli_commit()

        self.assertTrue(is_systemd_service_active(tuned_service))

        self.assertEqual(sysctl_read('net.ipv4.neigh.default.gc_thresh1'), gc_thresh1)
        self.assertEqual(sysctl_read('net.ipv4.neigh.default.gc_thresh2'), gc_thresh2)
        self.assertEqual(sysctl_read('net.ipv4.neigh.default.gc_thresh3'), gc_thresh3)

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
