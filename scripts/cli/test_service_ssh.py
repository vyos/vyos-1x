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

import re
import os
import unittest

from psutil import process_iter
from vyos.configsession import ConfigSession, ConfigSessionError
from vyos.util import read_file

SSHD_CONF = '/etc/ssh/sshd_config'
base_path = ['service', 'ssh']

def get_config_value(key):
    tmp = read_file(SSHD_CONF)
    tmp = re.findall(r'\n?{}\s+(.*)'.format(key), tmp)
    return tmp[0]


class TestServiceSSH(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        self.session.delete(base_path)

    def tearDown(self):
        del self.session

    def test_ssh(self):
        """ Check if SSH service can be configured and runs """
        self.session.set(base_path + ['port', '2222'])
        self.session.set(base_path + ['disable-host-validation'])
        self.session.set(base_path + ['disable-password-authentication'])

        # commit changes
        self.session.commit()

        # Check configured port
        port = get_config_value('Port')
        self.assertTrue("2222" in port)

        # Check DNS usage
        dns = get_config_value('UseDNS')
        self.assertTrue("no" in dns)

        # Check PasswordAuthentication
        pwd = get_config_value('PasswordAuthentication')
        self.assertTrue("no" in pwd)

        # Check for running process
        self.assertTrue("sshd" in (p.name() for p in process_iter()))

if __name__ == '__main__':
    unittest.main()
