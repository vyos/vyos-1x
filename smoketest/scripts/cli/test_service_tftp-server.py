#!/usr/bin/env python3
#
# Copyright (C) 2019-2023 VyOS maintainers and contributors
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

from psutil import process_iter
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.process import cmd
from vyos.utils.file import read_file
from vyos.utils.process import process_named_running
from vyos.template import is_ipv6

PROCESS_NAME = 'in.tftpd'
base_path = ['service', 'tftp-server']
dummy_if_path = ['interfaces', 'dummy', 'dum69']
address_ipv4 = '192.0.2.1'
address_ipv6 = '2001:db8::1'
vrf = 'mgmt'

class TestServiceTFTPD(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestServiceTFTPD, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

        cls.cli_set(cls, dummy_if_path + ['address', address_ipv4 + '/32'])
        cls.cli_set(cls, dummy_if_path + ['address', address_ipv6 + '/128'])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, dummy_if_path)
        super(TestServiceTFTPD, cls).tearDownClass()

    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        self.cli_delete(base_path)
        self.cli_commit()

        # Check for no longer running process
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_01_tftpd_single(self):
        directory = '/tmp'
        port = '69' # default port

        self.cli_set(base_path + ['allow-upload'])
        self.cli_set(base_path + ['directory', directory])
        self.cli_set(base_path + ['listen-address', address_ipv4])

        # commit changes
        self.cli_commit()

        config = read_file('/etc/default/tftpd0')
        # verify listen IP address
        self.assertIn(f'{address_ipv4}:{port} -4', config)
        # verify directory
        self.assertIn(directory, config)
        # verify upload
        self.assertIn('--create --umask 000', config)

    def test_02_tftpd_multi(self):
        directory = '/tmp'
        address = [address_ipv4, address_ipv6]
        port = '70'

        self.cli_set(base_path + ['directory', directory])
        for addr in address:
            self.cli_set(base_path + ['listen-address', addr])
            self.cli_set(base_path + ['port', port])

        # commit changes
        self.cli_commit()

        for idx in range(0, len(address)):
            config = read_file(f'/etc/default/tftpd{idx}')
            addr = address[idx]

            # verify listen IP address
            if is_ipv6(addr):
                addr = f'[{addr}]'
                self.assertIn(f'{addr}:{port} -6', config)
            else:
                self.assertIn(f'{addr}:{port} -4', config)

            # verify directory
            self.assertIn(directory, config)

        # Check for running processes - one process is spawned per listen
        # IP address, wheter it's IPv4 or IPv6
        count = 0
        for p in process_iter():
            if PROCESS_NAME in p.name():
                count += 1
        self.assertEqual(count, len(address))

    def test_03_tftpd_vrf(self):
        directory = '/tmp'
        port = '69' # default port

        self.cli_set(base_path + ['allow-upload'])
        self.cli_set(base_path + ['directory', directory])
        self.cli_set(base_path + ['listen-address', address_ipv4, 'vrf', vrf])

        # VRF does yet not exist - an error must be thrown
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(['vrf', 'name', vrf, 'table', '1338'])
        self.cli_set(dummy_if_path + ['vrf', vrf])

        # commit changes
        self.cli_commit()

        config = read_file('/etc/default/tftpd0')
        # verify listen IP address
        self.assertIn(f'{address_ipv4}:{port} -4', config)
        # verify directory
        self.assertIn(directory, config)
        # verify upload
        self.assertIn('--create --umask 000', config)

        # Check for process in VRF
        tmp = cmd(f'ip vrf pids {vrf}')
        self.assertIn(PROCESS_NAME, tmp)

        # delete VRF
        self.cli_delete(dummy_if_path + ['vrf'])
        self.cli_delete(['vrf', 'name', vrf])

if __name__ == '__main__':
    unittest.main(verbosity=2)
