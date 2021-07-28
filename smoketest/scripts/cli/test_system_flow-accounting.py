#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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
from vyos.util import cmd
from vyos.util import process_named_running
from vyos.util import read_file

PROCESS_NAME = 'uacctd'
base_path = ['system', 'flow-accounting']

uacctd_conf = '/etc/pmacct/uacctd.conf'

class TestSystemFlowAccounting(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(cls, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        # after service removal process must no longer run
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_basic(self):
        buffer_size = '5' # MiB
        self.cli_set(base_path + ['buffer-size', buffer_size])

        # You need to configure at least one interface for flow-accounting
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for interface in Section.interfaces('ethernet'):
            self.cli_set(base_path + ['interface', interface])

        # commit changes
        self.cli_commit()

        # verify configuration
        nftables_output = cmd('sudo nft list chain raw VYOS_CT_PREROUTING_HOOK').splitlines()
        for interface in Section.interfaces('ethernet'):
            rule_found = False
            ifname_search = f'iifname "{interface}"'

            for nftables_line in nftables_output:
                if 'FLOW_ACCOUNTING_RULE' in nftables_line and ifname_search in nftables_line:
                    self.assertIn('group 2', nftables_line)
                    self.assertIn('snaplen 128', nftables_line)
                    self.assertIn('queue-threshold 100', nftables_line)
                    rule_found = True
                    break

            self.assertTrue(rule_found)

        uacctd = read_file(uacctd_conf)
        # circular queue size - buffer_size
        tmp = int(buffer_size) *1024 *1024
        self.assertIn(f'plugin_pipe_size: {tmp}', uacctd)
        # transfer buffer size - recommended value from pmacct developers 1/1000 of pipe size
        tmp = int(buffer_size) *1024 *1024
        # do an integer division
        tmp //= 1000
        self.assertIn(f'plugin_buffer_size: {tmp}', uacctd)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    unittest.main(verbosity=2)
