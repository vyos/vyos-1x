#!/usr/bin/env python3
#
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
from vyos.util import process_named_running

base_path = ['service', 'mdns', 'repeater']
intf_base = ['interfaces', 'dummy']

class TestServiceMDNSrepeater(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())

    def tearDown(self):
        self.session.delete(base_path)
        self.session.delete(intf_base + ['dum10'])
        self.session.delete(intf_base + ['dum20'])
        self.session.commit()
        del self.session

    def test_service(self):
        # Service required a configured IP address on the interface

        self.session.set(intf_base + ['dum10', 'address', '192.0.2.1/30'])
        self.session.set(intf_base + ['dum20', 'address', '192.0.2.5/30'])

        self.session.set(base_path + ['interface', 'dum10'])
        self.session.set(base_path + ['interface', 'dum20'])
        self.session.commit()

        # Check for running process
        self.assertTrue(process_named_running('mdns-repeater'))

if __name__ == '__main__':
    unittest.main()
