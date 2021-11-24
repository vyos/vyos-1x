#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.template import is_ipv4
from vyos.template import address_from_cidr
from vyos.util import read_file
from vyos.util import process_named_running

PROCESS_NAME = 'snmpd'
SNMPD_CONF = '/etc/snmp/snmpd.conf'

base_path = ['service', 'snmp']

def get_config_value(key):
    tmp = read_file(SNMPD_CONF)
    tmp = re.findall(r'\n?{}\s+(.*)'.format(key), tmp)
    return tmp[0]

class TestSNMPService(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(cls, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        # delete testing SNMP config
        self.cli_delete(base_path)
        self.cli_commit()

    def test_snmp_basic(self):
        dummy_if = 'dum7312'
        dummy_addr = '100.64.0.1/32'
        self.cli_set(['interfaces', 'dummy', dummy_if, 'address', dummy_addr])

        # Check if SNMP can be configured and service runs
        clients = ['192.0.2.1', '2001:db8::1']
        networks = ['192.0.2.128/25', '2001:db8:babe::/48']
        listen = ['127.0.0.1', '::1', address_from_cidr(dummy_addr)]
        port = '5000'

        for auth in ['ro', 'rw']:
            community = 'VyOS' + auth
            self.cli_set(base_path + ['community', community, 'authorization', auth])
            for client in clients:
                self.cli_set(base_path + ['community', community, 'client', client])
            for network in networks:
                self.cli_set(base_path + ['community', community, 'network', network])

        for addr in listen:
            self.cli_set(base_path + ['listen-address', addr, 'port', port])

        self.cli_set(base_path + ['contact', 'maintainers@vyos.io'])
        self.cli_set(base_path + ['location', 'qemu'])

        self.cli_commit()

        # verify listen address, it will be returned as
        # ['unix:/run/snmpd.socket,udp:127.0.0.1:161,udp6:[::1]:161']
        # thus we need to transfor this into a proper list
        config = get_config_value('agentaddress')
        expected = 'unix:/run/snmpd.socket'
        self.assertIn(expected, config)

        for addr in listen:
            if is_ipv4(addr):
                expected = f'udp:{addr}:{port}'
            else:
                expected = f'udp6:[{addr}]:{port}'
            self.assertIn(expected, config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))
        self.cli_delete(['interfaces', 'dummy', dummy_if])


    def test_snmpv3_sha(self):
        # Check if SNMPv3 can be configured with SHA authentication
        # and service runs

        self.cli_set(base_path + ['v3', 'engineid', '000000000000000000000002'])
        self.cli_set(base_path + ['v3', 'group', 'default', 'mode', 'ro'])
        # check validate() - a view must be created before this can be committed
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['v3', 'view', 'default', 'oid', '1'])
        self.cli_set(base_path + ['v3', 'group', 'default', 'view', 'default'])

        # create user
        self.cli_set(base_path + ['v3', 'user', 'vyos', 'auth', 'plaintext-password', 'vyos12345678'])
        self.cli_set(base_path + ['v3', 'user', 'vyos', 'auth', 'type', 'sha'])
        self.cli_set(base_path + ['v3', 'user', 'vyos', 'privacy', 'plaintext-password', 'vyos12345678'])
        self.cli_set(base_path + ['v3', 'user', 'vyos', 'privacy', 'type', 'aes'])
        self.cli_set(base_path + ['v3', 'user', 'vyos', 'group', 'default'])

        self.cli_commit()

        # commit will alter the CLI values - check if they have been updated:
        hashed_password = '4e52fe55fd011c9c51ae2c65f4b78ca93dcafdfe'
        tmp = self._session.show_config(base_path + ['v3', 'user', 'vyos', 'auth', 'encrypted-password']).split()[1]
        self.assertEqual(tmp, hashed_password)

        tmp = self._session.show_config(base_path + ['v3', 'user', 'vyos', 'privacy', 'encrypted-password']).split()[1]
        self.assertEqual(tmp, hashed_password)

        # TODO: read in config file and check values

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_snmpv3_md5(self):
        # Check if SNMPv3 can be configured with MD5 authentication
        # and service runs

        self.cli_set(base_path + ['v3', 'engineid', '000000000000000000000002'])
        self.cli_set(base_path + ['v3', 'group', 'default', 'mode', 'ro'])
        # check validate() - a view must be created before this can be comitted
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['v3', 'view', 'default', 'oid', '1'])
        self.cli_set(base_path + ['v3', 'group', 'default', 'view', 'default'])

        # create user
        self.cli_set(base_path + ['v3', 'user', 'vyos', 'auth', 'plaintext-password', 'vyos12345678'])
        self.cli_set(base_path + ['v3', 'user', 'vyos', 'auth', 'type', 'md5'])
        self.cli_set(base_path + ['v3', 'user', 'vyos', 'privacy', 'plaintext-password', 'vyos12345678'])
        self.cli_set(base_path + ['v3', 'user', 'vyos', 'privacy', 'type', 'des'])
        self.cli_set(base_path + ['v3', 'user', 'vyos', 'group', 'default'])

        self.cli_commit()

        # commit will alter the CLI values - check if they have been updated:
        hashed_password = '4c67690d45d3dfcd33d0d7e308e370ad'
        tmp = self._session.show_config(base_path + ['v3', 'user', 'vyos', 'auth', 'encrypted-password']).split()[1]
        self.assertEqual(tmp, hashed_password)

        tmp = self._session.show_config(base_path + ['v3', 'user', 'vyos', 'privacy', 'encrypted-password']).split()[1]
        self.assertEqual(tmp, hashed_password)

        # TODO: read in config file and check values

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    unittest.main(verbosity=2)
