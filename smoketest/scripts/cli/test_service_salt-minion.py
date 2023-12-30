#!/usr/bin/env python3
#
# Copyright (C) 2022-2023 VyOS maintainers and contributors
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

from socket import gethostname
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.utils.process import process_named_running
from vyos.utils.file import read_file
from vyos.utils.process import cmd

PROCESS_NAME = 'salt-minion'
SALT_CONF = '/etc/salt/minion'
base_path = ['service', 'salt-minion']

interface = 'dum4456'

class TestServiceSALT(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestServiceSALT, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

        cls.cli_set(cls, ['interfaces', 'dummy', interface, 'address', '100.64.0.1/16'])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['interfaces', 'dummy', interface])
        super(TestServiceSALT, cls).tearDownClass()

    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        # delete testing SALT config
        self.cli_delete(base_path)
        self.cli_commit()

        # For an unknown reason on QEMU systems (e.g. where smoketests are executed
        # from the CI) salt-minion process is not killed by systemd. Apparently
        # no issue on VMWare.
        if cmd('systemd-detect-virt') != 'kvm':
            self.assertFalse(process_named_running(PROCESS_NAME))

    def test_default(self):
        servers = ['192.0.2.1', '192.0.2.2']

        for server in servers:
            self.cli_set(base_path + ['master', server])

        self.cli_commit()

        # commiconf = read_file() Check configured port
        conf = read_file(SALT_CONF)
        self.assertIn(f'  - {server}', conf)

        # defaults
        hostname = gethostname()
        self.assertIn(f'hash_type: sha256', conf)
        self.assertIn(f'id: {hostname}', conf)
        self.assertIn(f'mine_interval: 60', conf)

    def test_options(self):
        server = '192.0.2.3'
        hash = 'sha1'
        id = 'foo'
        interval = '120'

        self.cli_set(base_path + ['master', server])
        self.cli_set(base_path + ['hash', hash])
        self.cli_set(base_path + ['id', id])
        self.cli_set(base_path + ['interval', interval])
        self.cli_set(base_path + ['source-interface', interface])

        self.cli_commit()

        # commiconf = read_file() Check configured port
        conf = read_file(SALT_CONF)
        self.assertIn(f'- {server}', conf)

        # defaults
        self.assertIn(f'hash_type: {hash}', conf)
        self.assertIn(f'id: {id}', conf)
        self.assertIn(f'mine_interval: {interval}', conf)
        self.assertIn(f'source_interface_name: {interface}', conf)

if __name__ == '__main__':
    unittest.main(verbosity=2)
