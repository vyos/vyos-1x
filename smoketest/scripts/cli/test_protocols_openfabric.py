#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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
from vyos.utils.process import process_named_running

PROCESS_NAME = 'fabricd'
base_path = ['protocols', 'openfabric']

domain = 'VyOS'
net = '49.0001.1111.1111.1111.00'
dummy_if = 'dum1234'
address_families = ['ipv4', 'ipv6']

path = base_path + ['domain', domain]

class TestProtocolsOpenFabric(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        # call base-classes classmethod
        super(TestProtocolsOpenFabric, cls).setUpClass()
        # Retrieve FRR daemon PID - it is not allowed to crash, thus PID must remain the same
        cls.daemon_pid = process_named_running(PROCESS_NAME)
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        # check process health and continuity
        self.assertEqual(self.daemon_pid, process_named_running(PROCESS_NAME))

    def openfabric_base_config(self):
        self.cli_set(['interfaces', 'dummy', dummy_if])
        self.cli_set(base_path + ['net', net])
        for family in address_families:
            self.cli_set(path + ['interface', dummy_if, 'address-family', family])

    def test_openfabric_01_router_params(self):
        fabric_tier = '5'
        lsp_gen_interval = '20'

        self.cli_set(base_path)

        # verify() - net id and domain name are mandatory
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.openfabric_base_config()

        self.cli_set(path + ['log-adjacency-changes'])
        self.cli_set(path + ['set-overload-bit'])
        self.cli_set(path + ['fabric-tier', fabric_tier])
        self.cli_set(path + ['lsp-gen-interval', lsp_gen_interval])

        # Commit all changes
        self.cli_commit()

        # Verify all changes
        tmp = self.getFRRconfig(f'router openfabric {domain}', daemon='fabricd')
        self.assertIn(f' net {net}', tmp)
        self.assertIn(f' log-adjacency-changes', tmp)
        self.assertIn(f' set-overload-bit', tmp)
        self.assertIn(f' fabric-tier {fabric_tier}', tmp)
        self.assertIn(f' lsp-gen-interval {lsp_gen_interval}', tmp)

        tmp = self.getFRRconfig(f'interface {dummy_if}', daemon='fabricd')
        self.assertIn(f' ip router openfabric {domain}', tmp)
        self.assertIn(f' ipv6 router openfabric {domain}', tmp)

    def test_openfabric_02_loopback_interface(self):
        interface = 'lo'
        hello_interval = '100'
        metric = '24478'

        self.openfabric_base_config()
        self.cli_set(path + ['interface', interface, 'address-family', 'ipv4'])

        self.cli_set(path + ['interface', interface, 'hello-interval', hello_interval])
        self.cli_set(path + ['interface', interface, 'metric', metric])

        # Commit all changes
        self.cli_commit()

        # Verify FRR openfabric configuration
        tmp = self.getFRRconfig(f'router openfabric {domain}', daemon='fabricd')
        self.assertIn(f'router openfabric {domain}', tmp)
        self.assertIn(f' net {net}', tmp)

        # Verify interface configuration
        tmp = self.getFRRconfig(f'interface {interface}', daemon='fabricd')
        self.assertIn(f' ip router openfabric {domain}', tmp)
        # for lo interface 'openfabric passive' is implied
        self.assertIn(f' openfabric passive', tmp)
        self.assertIn(f' openfabric metric {metric}', tmp)

    def test_openfabric_03_password(self):
        password = 'foo'

        self.openfabric_base_config()

        self.cli_set(path + ['interface', dummy_if, 'password', 'plaintext-password', f'{password}-{dummy_if}'])
        self.cli_set(path + ['interface', dummy_if, 'password', 'md5', f'{password}-{dummy_if}'])

        # verify() - can not use both md5 and plaintext-password for password for the interface
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['interface', dummy_if, 'password', 'md5'])

        self.cli_set(path + ['domain-password', 'plaintext-password', password])
        self.cli_set(path + ['domain-password', 'md5', password])

        # verify() - can not use both md5 and plaintext-password for domain-password
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['domain-password', 'md5'])

        # Commit all changes
        self.cli_commit()

        # Verify all changes
        tmp = self.getFRRconfig(f'router openfabric {domain}', daemon='fabricd')
        self.assertIn(f' net {net}', tmp)
        self.assertIn(f' domain-password clear {password}', tmp)

        tmp = self.getFRRconfig(f'interface {dummy_if}', daemon='fabricd')
        self.assertIn(f' openfabric password clear {password}-{dummy_if}', tmp)

    def test_openfabric_multiple_domains(self):
        domain_2 = 'VyOS_2'
        interface = 'dum5678'
        new_path = base_path + ['domain', domain_2]

        self.openfabric_base_config()

        # set same interface for 2 OpenFabric domains
        self.cli_set(['interfaces', 'dummy', interface])
        self.cli_set(new_path + ['interface', interface, 'address-family', 'ipv4'])
        self.cli_set(path + ['interface', interface, 'address-family', 'ipv4'])

        # verify() - same interface can be used only for one OpenFabric instance
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(path + ['interface', interface])

        # Commit all changes
        self.cli_commit()

        # Verify FRR openfabric configuration
        tmp = self.getFRRconfig(f'router openfabric {domain}', daemon='fabricd')
        self.assertIn(f'router openfabric {domain}', tmp)
        self.assertIn(f' net {net}', tmp)

        tmp = self.getFRRconfig(f'router openfabric {domain_2}', daemon='fabricd')
        self.assertIn(f'router openfabric {domain_2}', tmp)
        self.assertIn(f' net {net}', tmp)

        # Verify interface configuration
        tmp = self.getFRRconfig(f'interface {dummy_if}', daemon='fabricd')
        self.assertIn(f' ip router openfabric {domain}', tmp)
        self.assertIn(f' ipv6 router openfabric {domain}', tmp)

        tmp = self.getFRRconfig(f'interface {interface}', daemon='fabricd')
        self.assertIn(f' ip router openfabric {domain_2}', tmp)


if __name__ == '__main__':
    unittest.main(verbosity=2)
