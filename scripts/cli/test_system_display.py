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

import re
import os
import unittest
import configparser

from psutil import process_iter
from vyos.configsession import ConfigSession, ConfigSessionError
from vyos.util import read_file

base_path = ['system', 'display']

"""
    system display model (sdec|ezio)
    system display show host (cpu|cpu-all|cpu-hist|disk|load-hist|memory|proc|uptime)
                        network interface <intName> alias <alias>
                                units (bps|Bps|pps)
                        clock (big|mini|date-time)
                        title <name>

    system display time <s>
    system display hello <string>
    system display bye <string>
    system display disabled
"""

class SystemDisplayTest(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())

    def tearDown(self):
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_system_display(self):
        # configure some system display
        self.session.set(base_path + ['hello', 'Welcome to VyOS'])
        self.session.set(base_path + ['bye', 'Bye from VyOS'])
        self.session.set(base_path + ['time', '30'])

        # check validate() - a model and a show are required
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

        self.session.set(base_path + ['model', 'ezio'])

        # check validate() - a show required
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

        self.session.set(base_path + ['show', 'clock', 'big'])

        self.session.set(base_path + ['show', 'network', 'units', 'pps'])
        self.session.set(base_path + ['show', 'network', 'interface', 'eth0', 'alias', 'WAN'])
        self.session.set(base_path + ['show', 'network', 'interface', 'eth1', 'alias', 'LAN'])
        self.session.set(base_path + ['show', 'network', 'interface', 'eth2', 'alias', 'WIFI'])
        # One too many
        self.session.set(base_path + ['show', 'network', 'interface', 'eth3'])

        # check validate() - more then 3 interfaces
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

        self.session.delete(base_path + ['show', 'network', 'interface', 'eth3'])

        # commit changes
        self.session.commit()

        # load up ini-styled LCDd.conf
        LCDd_conf = configparser.ConfigParser()
        LCDd_conf.read('/run/LCDd/LCDd.lo.conf')

        # Check settings made it into LCDd.conf
        self.assertTrue(LCDd_conf['server']['Driver'] == 'hd44780')
        self.assertTrue(LCDd_conf['server']['Hello'] == '"Welcome to VyOS"')
        self.assertTrue(LCDd_conf['server']['GoodBye'] == '"Bye from VyOS"')
        self.assertTrue(LCDd_conf['server']['WaitTime'] == '30')

        self.assertTrue(LCDd_conf['hd44780']['ConnectionType'] == 'ezio')
        self.assertTrue(LCDd_conf['hd44780']['Keypad'] == 'yes')
        self.assertTrue(LCDd_conf['hd44780']['Size'] == '16x2')
        self.assertTrue(LCDd_conf['hd44780']['KeyMatrix_4_1'] == 'Enter')
        self.assertTrue(LCDd_conf['hd44780']['KeyMatrix_4_2'] == 'Up')
        self.assertTrue(LCDd_conf['hd44780']['KeyMatrix_4_3'] == 'Down')
        self.assertTrue(LCDd_conf['hd44780']['KeyMatrix_4_4'] == 'Escape')
       #self.assertTrue(LCDd_conf['hd44780']['Device'] == '/dev/ttyS1')

        # load up ini-styled lcdproc.conf configuration file
        lcdproc_conf = configparser.ConfigParser()

        lcdproc_conf.read('/run/lcdproc/lcdproc.lo.conf')
        # clock
        self.assertTrue(lcdproc_conf['TimeDate']['Active'] == 'false')
        self.assertTrue(lcdproc_conf['BigClock']['Active'] == 'true')
        self.assertTrue(lcdproc_conf['MiniClock']['Active'] == 'false')
        # host
        self.assertTrue(lcdproc_conf['CPU']['Active'] == 'false')
        self.assertTrue(lcdproc_conf['Memory']['Active'] == 'false')
        self.assertTrue(lcdproc_conf['Load']['Active'] == 'false')
        # network
        self.assertTrue(lcdproc_conf['Iface']['Active'] == 'true')
        self.assertTrue(lcdproc_conf['Iface']['Interface0'] == 'eth0')
        self.assertTrue(lcdproc_conf['Iface']['Alias0'] == 'WAN')
        self.assertTrue(lcdproc_conf['Iface']['Interface1'] == 'eth1')
        self.assertTrue(lcdproc_conf['Iface']['Alias1'] == 'LAN')
        self.assertTrue(lcdproc_conf['Iface']['Interface2'] == 'eth2')
        self.assertTrue(lcdproc_conf['Iface']['Alias2'] == 'WIFI')
        self.assertTrue(lcdproc_conf['Iface']['unit'] == 'packet')
        # Check if LCdd and lcdproc are running
        running = 0
        for p in process_iter():
            if p.name() in ['lcdproc', 'LCDd']:
                running += 1

        # both processes running
        self.assertTrue(running == 2)

if __name__ == '__main__':
    unittest.main()
