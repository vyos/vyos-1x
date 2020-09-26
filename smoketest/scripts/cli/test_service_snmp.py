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

import os
import re
import unittest

from vyos.validate import is_ipv4

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import read_file
from vyos.util import process_named_running

PROCESS_NAME = 'snmpd'
SNMPD_CONF = '/etc/snmp/snmpd.conf'

base_path = ['service', 'snmp']

def get_config_value(key):
    tmp = read_file(SNMPD_CONF)
    tmp = re.findall(r'\n?{}\s+(.*)'.format(key), tmp)
    return tmp[0]

class TestSNMPService(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        self.session.delete(base_path)

    def tearDown(self):
        del self.session

    def test_snmp(self):
        """ Check if SNMP can be configured and service runs """
        clients = ['192.0.2.1', '2001:db8::1']
        networks = ['192.0.2.128/25', '2001:db8:babe::/48']
        listen = ['127.0.0.1', '::1']

        for auth in ['ro', 'rw']:
            community = 'VyOS' + auth
            self.session.set(base_path + ['community', community, 'authorization', auth])
            for client in clients:
                self.session.set(base_path + ['community', community, 'client', client])
            for network in networks:
                self.session.set(base_path + ['community', community, 'network', network])

        for addr in listen:
            self.session.set(base_path + ['listen-address', addr])

        self.session.set(base_path + ['contact', 'maintainers@vyos.io'])
        self.session.set(base_path + ['location', 'qemu'])

        self.session.commit()

        # verify listen address, it will be returned as
        # ['unix:/run/snmpd.socket,udp:127.0.0.1:161,udp6:[::1]:161']
        # thus we need to transfor this into a proper list
        config = get_config_value('agentaddress')
        expected = 'unix:/run/snmpd.socket'
        for addr in listen:
            if is_ipv4(addr):
                expected += ',udp:{}:161'.format(addr)
            else:
                expected += ',udp6:[{}]:161'.format(addr)

        self.assertTrue(expected in config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))


    def test_snmpv3_sha(self):
        """ Check if SNMPv3 can be configured with SHA authentication and service runs"""

        self.session.set(base_path + ['v3', 'engineid', '000000000000000000000002'])
        self.session.set(base_path + ['v3', 'group', 'default', 'mode', 'ro'])
        # check validate() - a view must be created before this can be comitted
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

        self.session.set(base_path + ['v3', 'view', 'default', 'oid', '1'])
        self.session.set(base_path + ['v3', 'group', 'default', 'view', 'default'])

        # create user
        self.session.set(base_path + ['v3', 'user', 'vyos', 'auth', 'plaintext-password', 'vyos12345678'])
        self.session.set(base_path + ['v3', 'user', 'vyos', 'auth', 'type', 'sha'])
        self.session.set(base_path + ['v3', 'user', 'vyos', 'privacy', 'plaintext-password', 'vyos12345678'])
        self.session.set(base_path + ['v3', 'user', 'vyos', 'privacy', 'type', 'aes'])
        self.session.set(base_path + ['v3', 'user', 'vyos', 'group', 'default'])

        self.session.commit()

        # commit will alter the CLI values - check if they have been updated:
        hashed_password = '4e52fe55fd011c9c51ae2c65f4b78ca93dcafdfe'
        tmp = self.session.show_config(base_path + ['v3', 'user', 'vyos', 'auth', 'encrypted-password']).split()[1]
        self.assertEqual(tmp, hashed_password)

        tmp = self.session.show_config(base_path + ['v3', 'user', 'vyos', 'privacy', 'encrypted-password']).split()[1]
        self.assertEqual(tmp, hashed_password)

        # TODO: read in config file and check values

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_snmpv3_md5(self):
        """ Check if SNMPv3 can be configured with MD5 authentication and service runs"""

        self.session.set(base_path + ['v3', 'engineid', '000000000000000000000002'])
        self.session.set(base_path + ['v3', 'group', 'default', 'mode', 'ro'])
        # check validate() - a view must be created before this can be comitted
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

        self.session.set(base_path + ['v3', 'view', 'default', 'oid', '1'])
        self.session.set(base_path + ['v3', 'group', 'default', 'view', 'default'])

        # create user
        self.session.set(base_path + ['v3', 'user', 'vyos', 'auth', 'plaintext-password', 'vyos12345678'])
        self.session.set(base_path + ['v3', 'user', 'vyos', 'auth', 'type', 'md5'])
        self.session.set(base_path + ['v3', 'user', 'vyos', 'privacy', 'plaintext-password', 'vyos12345678'])
        self.session.set(base_path + ['v3', 'user', 'vyos', 'privacy', 'type', 'des'])
        self.session.set(base_path + ['v3', 'user', 'vyos', 'group', 'default'])

        self.session.commit()

        # commit will alter the CLI values - check if they have been updated:
        hashed_password = '4c67690d45d3dfcd33d0d7e308e370ad'
        tmp = self.session.show_config(base_path + ['v3', 'user', 'vyos', 'auth', 'encrypted-password']).split()[1]
        self.assertEqual(tmp, hashed_password)

        tmp = self.session.show_config(base_path + ['v3', 'user', 'vyos', 'privacy', 'encrypted-password']).split()[1]
        self.assertEqual(tmp, hashed_password)

        # TODO: read in config file and check values

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    unittest.main()

