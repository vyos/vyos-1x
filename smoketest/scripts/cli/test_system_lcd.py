#!/usr/bin/env python3
#
# Copyright (C) 2020 Francois Mertz fireboxled@gmail.com
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

from configparser import ConfigParser
from vyos.configsession import ConfigSession
from vyos.util import process_named_running

config_file = '/run/LCDd/LCDd.conf'
base_path = ['system', 'lcd']

class TestSystemLCD(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())

    def tearDown(self):
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_system_display(self):
        # configure some system display
        self.session.set(base_path + ['device', 'ttyS1'])
        self.session.set(base_path + ['model', 'cfa-533'])

        # commit changes
        self.session.commit()

        # load up ini-styled LCDd.conf
        conf = ConfigParser()
        conf.read(config_file)

        self.assertEqual(conf['CFontzPacket']['Model'], '533')
        self.assertEqual(conf['CFontzPacket']['Device'], '/dev/ttyS1')

        # Check for running process
        self.assertTrue(process_named_running('LCDd'))

if __name__ == '__main__':
    unittest.main()
