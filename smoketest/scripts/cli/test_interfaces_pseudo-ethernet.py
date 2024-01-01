#!/usr/bin/env python3
#
# Copyright (C) 2020-2022 VyOS maintainers and contributors
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

from vyos.ifconfig import Section
from base_interfaces_test import BasicInterfaceTest

class PEthInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'pseudo-ethernet']

        cls._options = {}
        # we need to filter out VLAN interfaces identified by a dot (.)
        # in their name - just in case!
        if 'TEST_ETH' in os.environ:
            for tmp in os.environ['TEST_ETH'].split():
                cls._options.update({f'p{tmp}' : [f'source-interface {tmp}']})

        else:
            for tmp in Section.interfaces('ethernet'):
                if '.' in tmp:
                    continue
                cls._options.update({f'p{tmp}' : [f'source-interface {tmp}']})

        cls._interfaces = list(cls._options)
        # call base-classes classmethod
        super(PEthInterfaceTest, cls).setUpClass()

if __name__ == '__main__':
    unittest.main(verbosity=2)
