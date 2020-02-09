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
import re
import unittest

from subprocess import Popen, PIPE
from vyos.config import Config
from vyos.configsession import ConfigSession, ConfigSessionError
import vyos.util as util

base_path = ['system', 'login']
users = ['vyos1', 'vyos2']

class TestSystemLogin(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        env = self.session.get_session_env()
        self.config = Config(session_env=env)

    def tearDown(self):
        # Delete SNNP configuration
        for user in users:
            self.session.delete(base_path + ['user', user])

        self.session.commit()
        del self.session

    def test_user(self):
        """ Check if user can be created and we can SSH to localhost """
        self.session.set(['service', 'ssh', 'port', '22'])

        for user in users:
            name = "VyOS Roxx " + user
            home_dir = "/tmp/" + user

            self.session.set(base_path + ['user', user, 'authentication', 'plaintext-password', user])
            self.session.set(base_path + ['user', user, 'full-name', 'VyOS Roxx'])
            self.session.set(base_path + ['user', user, 'home-directory', home_dir])

        self.session.commit()

        for user in users:
            cmd = ['su','-', user]
            proc = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            tmp = "{}\nuname -a".format(user)
            proc.stdin.write(tmp.encode())
            proc.stdin.flush()
            (stdout, stderr) = proc.communicate()

            # stdout is something like this:
            # b'Linux vyos 4.19.101-amd64-vyos #1 SMP Sun Feb 2 10:18:07 UTC 2020 x86_64 GNU/Linux\n'
            self.assertTrue(len(stdout) > 40)

if __name__ == '__main__':
    unittest.main()
