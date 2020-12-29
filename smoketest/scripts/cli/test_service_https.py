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

from vyos.configsession import ConfigSession
from vyos.util import run

base_path = ['service', 'https']

class TestHTTPSService(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        self.session.delete(base_path)

    def tearDown(self):
        self.session.delete(base_path)
        self.session.commit()

    def test_default(self):
        self.session.set(base_path)
        self.session.commit()

        ret = run('sudo /usr/sbin/nginx -t')
        self.assertEqual(ret, 0)

    def test_server_block(self):
        vhost_id = 'example'
        address = '0.0.0.0'
        port = '8443'
        name = 'example.org'

        test_path = base_path + ['virtual-host', vhost_id]

        self.session.set(test_path + ['listen-address', address])
        self.session.set(test_path + ['listen-port', port])
        self.session.set(test_path + ['server-name', name])

        self.session.commit()

        ret = run('sudo /usr/sbin/nginx -t')
        self.assertEqual(ret, 0)

if __name__ == '__main__':
    unittest.main(verbosity=2)
