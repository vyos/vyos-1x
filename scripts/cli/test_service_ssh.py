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
    return tmp

class TestServiceSSH(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        self.session.delete(base_path)

    def tearDown(self):
        # delete testing SSH config
        self.session.delete(base_path)
        # restore "plain" SSH access
        self.session.set(base_path)

        self.session.commit()
        del self.session

    def test_ssh_single(self):
        """ Check if SSH service can be configured and runs """
        self.session.set(base_path + ['port', '1234'])
        self.session.set(base_path + ['disable-host-validation'])
        self.session.set(base_path + ['disable-password-authentication'])
        self.session.set(base_path + ['loglevel', 'verbose'])
        self.session.set(base_path + ['client-keepalive-interval', '100'])
        self.session.set(base_path + ['listen-address', '127.0.0.1'])

        # commit changes
        self.session.commit()

        # Check configured port
        port = get_config_value('Port')[0]
        self.assertTrue("1234" in port)

        # Check DNS usage
        dns = get_config_value('UseDNS')[0]
        self.assertTrue("no" in dns)

        # Check PasswordAuthentication
        pwd = get_config_value('PasswordAuthentication')[0]
        self.assertTrue("no" in pwd)

        # Check loglevel
        loglevel = get_config_value('LogLevel')[0]
        self.assertTrue("VERBOSE" in loglevel)

        # Check listen address
        address = get_config_value('ListenAddress')[0]
        self.assertTrue("127.0.0.1" in address)

        # Check keepalive
        keepalive = get_config_value('ClientAliveInterval')[0]
        self.assertTrue("100" in keepalive)

        # Check for running process
        self.assertTrue("sshd" in (p.name() for p in process_iter()))

    def test_ssh_multi(self):
        """ Check if SSH service can be configured and runs with multiple
            listen ports and listen-addresses """
        ports = ['22', '2222']
        for port in ports:
            self.session.set(base_path + ['port', port])

        addresses = ['127.0.0.1', '::1']
        for address in addresses:
            self.session.set(base_path + ['listen-address', address])

        # commit changes
        self.session.commit()

        # Check configured port
        tmp = get_config_value('Port')
        for port in ports:
            self.assertIn(port, tmp)

        # Check listen address
        tmp = get_config_value('ListenAddress')
        for address in addresses:
            self.assertIn(address, tmp)

        # Check for running process
        self.assertTrue("sshd" in (p.name() for p in process_iter()))

if __name__ == '__main__':
    unittest.main()
