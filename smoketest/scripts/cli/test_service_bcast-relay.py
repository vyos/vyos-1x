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
from vyos.configsession import ConfigSession, ConfigSessionError

base_path = ['service', 'broadcast-relay']

class TestServiceBroadcastRelay(unittest.TestCase):
    _address1 = '192.0.2.1/24'
    _address2 = '192.0.2.1/24'

    def setUp(self):
        self.session = ConfigSession(os.getpid())
        self.session.set(['interfaces', 'dummy', 'dum1001', 'address', self._address1])
        self.session.set(['interfaces', 'dummy', 'dum1002', 'address', self._address2])
        self.session.commit()

    def tearDown(self):
        self.session.delete(['interfaces', 'dummy', 'dum1001'])
        self.session.delete(['interfaces', 'dummy', 'dum1002'])
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_broadcast_relay_service(self):
        ids = range(1, 5)
        for id in ids:
            base = base_path + ['id', str(id)]
            self.session.set(base + ['description', 'vyos'])
            self.session.set(base + ['port', str(10000 + id)])

            # check validate() - two interfaces must be present
            with self.assertRaises(ConfigSessionError):
                self.session.commit()

            self.session.set(base + ['interface', 'dum1001'])
            self.session.set(base + ['interface', 'dum1002'])
            self.session.set(base + ['address', self._address1.split('/')[0]])

        self.session.commit()

        for id in ids:
            # check if process is running
            running = False
            for p in process_iter():
                if "udp-broadcast-relay" in p.name():
                    if p.cmdline()[3] == str(id):
                        running = True
                        break
            self.assertTrue(running)

if __name__ == '__main__':
    unittest.main(verbosity=2)
