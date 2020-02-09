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

from psutil import process_iter
from vyos.config import Config
from vyos.configsession import ConfigSession, ConfigSessionError

base_path = ['service', 'ssh']

class TestServiceSSH(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        env = self.session.get_session_env()
        self.config = Config(session_env=env)

    def tearDown(self):
        # Delete SSH configuration
        self.session.delete(base_path)
        self.session.commit()

        del self.session

    def test_ssh(self):
        """ Check if SSH service can be configured and runs """
        self.session.set(base_path)

        # Check for running process
        self.assertTrue("sshd" in (p.name() for p in process_iter()))

if __name__ == '__main__':
    unittest.main()
