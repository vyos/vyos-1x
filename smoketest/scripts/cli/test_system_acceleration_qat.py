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

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError

base_path = ['system', 'acceleration', 'qat']

class TestSystemLCD(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())

    def tearDown(self):
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_basic(self):
        """ Check if configuration script is in place and that the config
        script throws an error as QAT device is not present in Qemu. This *must*
        be extended with QAT autodetection once run on a QAT enabled device """

        # configure some system display
        self.session.set(base_path)

        # An error must be thrown if QAT device could not be found
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

if __name__ == '__main__':
    unittest.main()
