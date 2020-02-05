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

from paramiko import SSHClient, WarningPolicy

import vyos.config
import vyos.configsession
import vyos.util as util

base_path = ['system', 'login']
users = ['vyos1', 'vyos2']

class TestSystemLoginServer(unittest.TestCase):
    def setUp(self):
        self.session = vyos.configsession.ConfigSession(os.getpid())
        env = self.session.get_session_env()
        self.config = vyos.config.Config(session_env=env)

    def tearDown(self):
        # Delete SNNP configuration
        for user in users:
            self.session.delete(base_path + ['user', user])

        self.session.commit()

    def test_user(self):
        """ Check if user can be created and we can SSH to localhost """

        for user in users:
            name = "VyOS Roxx " + user
            home_dir = "/tmp/" + user

            self.session.set(base_path + ['user', user, 'authentication', 'plaintext-password', user])
            self.session.set(base_path + ['user', user, 'full-name', 'VyOS Roxx'])
            self.session.set(base_path + ['user', user, 'home-directory', home_dir])

        self.session.commit()

        # check if we can login via SSH
        for user in users:
            # check if homedir has been created
            self.assertTrue(os.path.isdir("/tmp/" + user))

            ssh = SSHClient()
            ssh.set_missing_host_key_policy(WarningPolicy)

            try:
                ssh.connect('localhost', username=user, password=user)
                stdin, stdout, stderr = ssh.exec_command('who')
                print(stdout.read().decode())
            except Exception as e:
                print(e)
                self.assertTrue(False)

            ssh.close()

            # check if homedir has been created
            # this can only be done after we have connected via ssh and
            # pam_mkhomedir was executes
            self.assertTrue(os.path.isdir("/tmp/" + user))

if __name__ == '__main__':
    unittest.main()
