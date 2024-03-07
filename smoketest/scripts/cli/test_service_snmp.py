#!/usr/bin/env python3
#
# Copyright (C) 2019-2021 VyOS maintainers and contributors
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
from vyos.utils.process import call
from vyos.utils.process import DEVNULL
from vyos.utils.file import read_file
from vyos.utils.process import process_named_running
from vyos.version import get_version_data

PROCESS_NAME = 'snmpd'
SNMPD_CONF = '/etc/snmp/snmpd.conf'

base_path = ['service', 'snmp']

snmpv3_group = 'default_group'
snmpv3_view = 'default_view'
snmpv3_view_oid = '1'
snmpv3_user = 'vyos'
snmpv3_auth_pw = 'vyos12345678'
snmpv3_priv_pw = 'vyos87654321'
snmpv3_engine_id = '000000000000000000000002'

def get_config_value(key):
    tmp = read_file(SNMPD_CONF)
    tmp = re.findall(r'\n?{}\s+(.*)'.format(key), tmp)
    return tmp[0]

class TestSNMPService(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSNMPService, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        # delete testing SNMP config
        self.cli_delete(base_path)
        self.cli_commit()

        # Check for running process
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_snmp_basic(self):
        dummy_if = 'dum7312'
        dummy_addr = '100.64.0.1/32'
        contact = 'maintainers@vyos.io'
        location = 'QEMU'

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

        self.cli_set(base_path + ['contact', contact])
        self.cli_set(base_path + ['location', location])

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

        config = get_config_value('sysDescr')
        version_data = get_version_data()
        self.assertEqual('VyOS ' + version_data['version'], config)

        config = get_config_value('SysContact')
        self.assertEqual(contact, config)

        config = get_config_value('SysLocation')
        self.assertEqual(location, config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))
        self.cli_delete(['interfaces', 'dummy', dummy_if])

        ## Check communities and default view RESTRICTED
        for auth in ['ro', 'rw']:
            community = 'VyOS' + auth
            for addr in clients:
                if is_ipv4(addr):
                    entry = auth + 'community ' + community + ' ' + addr + ' -V'
                else:
                    entry = auth + 'community6 ' + community + ' ' + addr + ' -V'
                config = get_config_value(entry)
                expected = 'RESTRICTED'
                self.assertIn(expected, config)
            for addr in networks:
                if is_ipv4(addr):
                    entry = auth + 'community ' + community + ' ' + addr + ' -V'
                else:
                    entry = auth + 'community6 ' + community + ' ' + addr + ' -V'
                config = get_config_value(entry)
                expected = 'RESTRICTED'
                self.assertIn(expected, config)
        # And finally check global entry for RESTRICTED view
        config = get_config_value('view RESTRICTED    included .1')
        self.assertIn('80', config)

    def test_snmpv3_sha(self):
        # Check if SNMPv3 can be configured with SHA authentication
        # and service runs
        self.cli_set(base_path + ['v3', 'engineid', snmpv3_engine_id])
        self.cli_set(base_path + ['v3', 'group', 'default', 'mode', 'ro'])
        # check validate() - a view must be created before this can be committed
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['v3', 'view', 'default', 'oid', '1'])
        self.cli_set(base_path + ['v3', 'group', 'default', 'view', 'default'])

        # create user
        self.cli_set(base_path + ['v3', 'user', snmpv3_user, 'auth', 'plaintext-password', snmpv3_auth_pw])
        self.cli_set(base_path + ['v3', 'user', snmpv3_user, 'auth', 'type', 'sha'])
        self.cli_set(base_path + ['v3', 'user', snmpv3_user, 'privacy', 'plaintext-password', snmpv3_priv_pw])
        self.cli_set(base_path + ['v3', 'user', snmpv3_user, 'privacy', 'type', 'aes'])
        self.cli_set(base_path + ['v3', 'user', snmpv3_user, 'group', 'default'])

        self.cli_commit()

        # commit will alter the CLI values - check if they have been updated:
        hashed_password = '4e52fe55fd011c9c51ae2c65f4b78ca93dcafdfe'
        tmp = self._session.show_config(base_path + ['v3', 'user', snmpv3_user, 'auth', 'encrypted-password']).split()[1]
        self.assertEqual(tmp, hashed_password)

        hashed_password = '54705c8de9e81fdf61ad7ac044fa8fe611ddff6b'
        tmp = self._session.show_config(base_path + ['v3', 'user', snmpv3_user, 'privacy', 'encrypted-password']).split()[1]
        self.assertEqual(tmp, hashed_password)

        # TODO: read in config file and check values

        # Try SNMPv3 connection
        tmp = call(f'snmpwalk -v 3 -u {snmpv3_user} -a SHA -A {snmpv3_auth_pw} -x AES -X {snmpv3_priv_pw} -l authPriv 127.0.0.1', stdout=DEVNULL)
        self.assertEqual(tmp, 0)

    def test_snmpv3_md5(self):
        # Check if SNMPv3 can be configured with MD5 authentication
        # and service runs
        self.cli_set(base_path + ['v3', 'engineid', snmpv3_engine_id])

        # create user
        self.cli_set(base_path + ['v3', 'user', snmpv3_user, 'auth', 'plaintext-password', snmpv3_auth_pw])
        self.cli_set(base_path + ['v3', 'user', snmpv3_user, 'auth', 'type', 'md5'])
        self.cli_set(base_path + ['v3', 'user', snmpv3_user, 'privacy', 'plaintext-password', snmpv3_priv_pw])
        self.cli_set(base_path + ['v3', 'user', snmpv3_user, 'privacy', 'type', 'des'])

        # check validate() - user requires a group to be created
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['v3', 'user', 'vyos', 'group', snmpv3_group])

        self.cli_set(base_path + ['v3', 'group', snmpv3_group, 'mode', 'ro'])
        # check validate() - a view must be created before this can be comitted
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['v3', 'view', snmpv3_view, 'oid', snmpv3_view_oid])
        self.cli_set(base_path + ['v3', 'group', snmpv3_group, 'view', snmpv3_view])

        self.cli_commit()

        # commit will alter the CLI values - check if they have been updated:
        hashed_password = '4c67690d45d3dfcd33d0d7e308e370ad'
        tmp = self._session.show_config(base_path + ['v3', 'user', 'vyos', 'auth', 'encrypted-password']).split()[1]
        self.assertEqual(tmp, hashed_password)

        hashed_password = 'e11c83f2c510540a3c4de84ee66de440'
        tmp = self._session.show_config(base_path + ['v3', 'user', 'vyos', 'privacy', 'encrypted-password']).split()[1]
        self.assertEqual(tmp, hashed_password)

        tmp = read_file(SNMPD_CONF)
        # views
        self.assertIn(f'view {snmpv3_view} included .{snmpv3_view_oid}', tmp)
        # group
        self.assertIn(f'group {snmpv3_group} usm {snmpv3_user}', tmp)
        # access
        self.assertIn(f'access {snmpv3_group} "" usm auth exact {snmpv3_view} none none', tmp)

        # Try SNMPv3 connection
        tmp = call(f'snmpwalk -v 3 -u {snmpv3_user} -a MD5 -A {snmpv3_auth_pw} -x DES -X {snmpv3_priv_pw} -l authPriv 127.0.0.1', stdout=DEVNULL)
        self.assertEqual(tmp, 0)

    def test_snmpv3_view_exclude(self):
        snmpv3_view_oid_exclude = ['1.3.6.1.2.1.4.21', '1.3.6.1.2.1.4.24']

        self.cli_set(base_path + ['v3', 'group', snmpv3_group, 'view', snmpv3_view])
        self.cli_set(base_path + ['v3', 'view', snmpv3_view, 'oid', snmpv3_view_oid])

        for excluded in snmpv3_view_oid_exclude:
            self.cli_set(base_path + ['v3', 'view', snmpv3_view, 'oid', snmpv3_view_oid, 'exclude', excluded])

        self.cli_commit()

        tmp = read_file(SNMPD_CONF)
        # views
        self.assertIn(f'view {snmpv3_view} included .{snmpv3_view_oid}', tmp)
        for excluded in snmpv3_view_oid_exclude:
            self.assertIn(f'view {snmpv3_view} excluded .{excluded}', tmp)

if __name__ == '__main__':
    unittest.main(verbosity=2)
