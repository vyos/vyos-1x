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

NTP_CONF = '/etc/ntp.conf'
base_path = ['system', 'ntp']

def get_config_value(key):
    tmp = read_file(NTP_CONF)
    tmp = re.findall(r'\n?{}\s+(.*)'.format(key), tmp)
    return tmp

class TestSystemNTP(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        self.session.delete(base_path)

    def tearDown(self):
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_ntp_options(self):
        servers = ['192.0.2.1', '192.0.2.2']
        options = ['noselect', 'preempt', 'prefer']

        for server in servers:
            for option in options:
                self.session.set(base_path + ['server', server, option])

        # commit changes
        self.session.commit()

        # Check configured port
        tmp = get_config_value('server')
        for server in servers:
            test = f'{server} iburst ' + ' '.join(options)
            self.assertTrue(test in tmp)

        # Check for running process
        self.assertTrue("ntpd" in (p.name() for p in process_iter()))

if __name__ == '__main__':
    unittest.main()
