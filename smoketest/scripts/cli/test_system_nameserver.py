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

from vyos.configsession import ConfigSession, ConfigSessionError
import vyos.util as util

RESOLV_CONF = '/etc/resolv.conf'

test_servers = ['192.0.2.10', '2001:db8:1::100']
base_path = ['system', 'name-server']

def get_name_servers():
    resolv_conf = util.read_file(RESOLV_CONF)
    return re.findall(r'\n?nameserver\s+(.*)', resolv_conf)

class TestSystemNameServer(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())

    def tearDown(self):
        # Delete existing name servers
        self.session.delete(base_path)
        self.session.commit()

        del self.session

    def test_nameserver_add(self):
        # Check if server is added to resolv.conf
        for s in test_servers:
            self.session.set(base_path + [s])
        self.session.commit()

        servers = get_name_servers()
        for s in servers:
            self.assertTrue(s in servers)

    def test_nameserver_delete(self):
        # Test if a deleted server disappears from resolv.conf
        for s in test_servers:
          self.session.delete(base_path + [s])
        self.session.commit()

        servers = get_name_servers()
        for s in servers:
            self.assertTrue(test_server_1 not in servers)

if __name__ == '__main__':
    unittest.main(verbosity=2)

