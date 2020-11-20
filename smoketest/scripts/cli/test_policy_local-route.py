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
from vyos.configsession import ConfigSessionError
from vyos.util import cmd
from vyos.util import process_named_running

class PolicyLocalRouteTest(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        self._sources = ['203.0.113.1', '203.0.113.2']

    def tearDown(self):
        # Delete all policies
        self.session.delete(['policy', 'local-route'])
        self.session.commit()
        del self.session

    # Test set table for some sources
    def test_table_id(self):
        base = ['policy', 'local-route']
        rule = '50'
        table = '23'
        for src in self._sources:
            self.session.set(base + ['rule', rule, 'set', 'table', table])
            self.session.set(base + ['rule', rule, 'source', src])

        self.session.commit()

        # Check generated configuration

        # Expected values
        original = """
        50:	from 203.0.113.1 lookup 23
        50:	from 203.0.113.2 lookup 23
        """
        tmp = cmd('ip rule show prio 50')
        original = original.split()
        tmp = tmp.split()

        self.assertEqual(tmp, original)

if __name__ == '__main__':
    unittest.main()
