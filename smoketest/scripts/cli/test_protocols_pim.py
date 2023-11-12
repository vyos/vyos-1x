#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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

import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Section
from vyos.utils.process import process_named_running

PROCESS_NAME = 'pimd'
base_path = ['protocols', 'pim']

class TestProtocolsPIM(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        # pimd process must be running
        self.assertTrue(process_named_running(PROCESS_NAME))

        self.cli_delete(base_path)
        self.cli_commit()

        # pimd process must be stopped by now
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_01_pim_basic(self):
        rp = '127.0.0.1'
        group = '224.0.0.0/4'
        hello = '100'
        dr_priority = '64'

        self.cli_set(base_path + ['rp', 'address', rp, 'group', group])

        interfaces = Section.interfaces('ethernet')
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface , 'bfd'])
            self.cli_set(base_path + ['interface', interface , 'dr-priority', dr_priority])
            self.cli_set(base_path + ['interface', interface , 'hello', hello])
            self.cli_set(base_path + ['interface', interface , 'no-bsm'])
            self.cli_set(base_path + ['interface', interface , 'no-unicast-bsm'])
            self.cli_set(base_path + ['interface', interface , 'passive'])

        # commit changes
        self.cli_commit()

        # Verify FRR pimd configuration
        frrconfig = self.getFRRconfig(daemon=PROCESS_NAME)
        self.assertIn(f'ip pim rp {rp} {group}', frrconfig)

        for interface in interfaces:
            frrconfig = self.getFRRconfig(f'interface {interface}', daemon=PROCESS_NAME)
            self.assertIn(f'interface {interface}', frrconfig)
            self.assertIn(f' ip pim', frrconfig)
            self.assertIn(f' ip pim bfd', frrconfig)
            self.assertIn(f' ip pim drpriority {dr_priority}', frrconfig)
            self.assertIn(f' ip pim hello {hello}', frrconfig)
            self.assertIn(f' no ip pim bsm', frrconfig)
            self.assertIn(f' no ip pim unicast-bsm', frrconfig)
            self.assertIn(f' ip pim passive', frrconfig)

        self.cli_commit()

    def test_02_pim_igmp_proxy(self):
        igmp_proxy = ['protocols', 'igmp-proxy']
        rp = '127.0.0.1'
        group = '224.0.0.0/4'
        hello = '100'
        dr_priority = '64'

        self.cli_set(base_path)
        self.cli_set(igmp_proxy)

        # check validate() - can not set both IGMP proxy and PIM
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(igmp_proxy)

        self.cli_set(base_path + ['rp', 'address', rp, 'group', group])
        interfaces = Section.interfaces('ethernet')
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface , 'bfd'])

        # commit changes
        self.cli_commit()

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
