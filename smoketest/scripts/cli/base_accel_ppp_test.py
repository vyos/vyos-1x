# Copyright (C) 2020 VyOS maintainers and contributors
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
from vyos.util import get_half_cpus
from vyos.validate import is_ipv4

nameserver = ['192.0.2.1', '192.0.2.2', '2001:db8::1']

class BasicAccelPPPTest:
    class BaseTest(unittest.TestCase):

        def setUp(self):
            self.session = ConfigSession(os.getpid())
            # ensure we can also run this test on a live system - so lets clean
            # out the current configuration :)
            self.session.delete(self._base_path)

        def tearDown(self):
            self.session.delete(self._base_path)
            self.session.commit()
            del self.session

        def set(self, path):
            self.session.set(self._base_path + path)

        def basic_config(self):
            # PPPoE local auth mode requires local users to be configured!
            self.set(['authentication', 'local-users', 'username', 'vyos', 'password', 'vyos'])
            self.set(['authentication', 'mode', 'local'])
            for ns in nameserver:
                self.set(['name-server', ns])

        def verify(self, conf):
            self.assertEqual(conf['core']['thread-count'], str(get_half_cpus()))
            # IPv4 and IPv6 nameservers must be checked individually
            for ns in nameserver:
                if is_ipv4(ns):
                    self.assertIn(ns, [conf['dns']['dns1'], conf['dns']['dns2']])
                else:
                    self.assertEqual(conf['ipv6-dns'][ns], None)

