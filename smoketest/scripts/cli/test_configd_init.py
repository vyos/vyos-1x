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
from time import sleep

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.utils.process import is_systemd_service_running
from vyos.utils.process import cmd

service_name = 'vyos-configd.service'

class TestConfigdInit(unittest.TestCase):
    def setUp(self):
        self.running_state = is_systemd_service_running(service_name)
        # always forward to base class
        super().setUp()

    def tearDown(self):
        if not self.running_state:
            cmd(f'sudo systemctl stop {service_name}')
        # always forward to base class
        super().tearDown()

    def test_configd_init(self):
        if not self.running_state:
            cmd(f'sudo systemctl start {service_name}')
            # allow time for init to succeed/fail
            sleep(2)
            self.assertTrue(is_systemd_service_running(service_name))

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
