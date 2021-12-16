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

import os
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.util import cmd
from vyos.util import process_named_running

base_path = ['protocols', 'rpki']
PROCESS_NAME = 'bgpd'

rpki_known_hosts = '/config/auth/known_hosts'
rpki_ssh_key = '/config/auth/id_rsa_rpki'
rpki_ssh_pub = f'{rpki_ssh_key}.pub'

class TestProtocolsRPKI(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        # Nothing RPKI specific should be left over in the config
        # frrconfig = self.getFRRconfig('rpki')
        # self.assertNotIn('rpki', frrconfig)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_rpki(self):
        polling = '7200'
        cache = {
            '192.0.2.1' : {
                'port' : '8080',
                'preference' : '1'
            },
            '192.0.2.2' : {
                'port' : '9090',
                'preference' : '2'
            },
            '2001:db8::1' : {
                'port' : '1234',
                'preference' : '3'
            },
            '2001:db8::2' : {
                'port' : '5678',
                'preference' : '4'
            },
        }

        self.cli_set(base_path + ['polling-period', polling])
        for peer, peer_config in cache.items():
            self.cli_set(base_path + ['cache', peer, 'port', peer_config['port']])
            self.cli_set(base_path + ['cache', peer, 'preference', peer_config['preference']])

        # commit changes
        self.cli_commit()

        # Verify FRR configuration
        frrconfig = self.getFRRconfig('rpki')
        self.assertIn(f'rpki polling_period {polling}', frrconfig)

        for peer, peer_config in cache.items():
            port = peer_config['port']
            preference = peer_config['preference']
            self.assertIn(f'rpki cache {peer} {port} preference {preference}', frrconfig)

    def test_rpki_ssh(self):
        self.skipTest('Currently untested, see: https://github.com/FRRouting/frr/issues/7978')
        polling = '7200'
        cache = {
            '192.0.2.3' : {
                'port' : '1234',
                'username' : 'foo',
                'preference' : '10'
            },
            '192.0.2.4' : {
                'port' : '5678',
                'username' : 'bar',
                'preference' : '20'
            },
        }

        self.cli_set(base_path + ['polling-period', polling])

        for peer, peer_config in cache.items():
            self.cli_set(base_path + ['cache', peer, 'port', peer_config['port']])
            self.cli_set(base_path + ['cache', peer, 'preference', peer_config['preference']])
            self.cli_set(base_path + ['cache', peer, 'ssh', 'username', peer_config['username']])
            self.cli_set(base_path + ['cache', peer, 'ssh', 'public-key-file', rpki_ssh_pub])
            self.cli_set(base_path + ['cache', peer, 'ssh', 'private-key-file', rpki_ssh_key])
            self.cli_set(base_path + ['cache', peer, 'ssh', 'known-hosts-file', rpki_known_hosts])

        # commit changes
        self.cli_commit()

        # Verify FRR configuration
        frrconfig = self.getFRRconfig('rpki')
        self.assertIn(f'rpki polling_period {polling}', frrconfig)

        for peer, peer_config in cache.items():
            port = peer_config['port']
            preference = peer_config['preference']
            username = peer_config['username']
            self.assertIn(f'rpki cache {peer} {port} {username} {rpki_ssh_key} {rpki_known_hosts} preference {preference}', frrconfig)


    def test_rpki_verify_preference(self):
        cache = {
            '192.0.2.1' : {
                'port' : '8080',
                'preference' : '1'
            },
            '192.0.2.2' : {
                'port' : '9090',
                'preference' : '1'
            },
        }

        for peer, peer_config in cache.items():
            self.cli_set(base_path + ['cache', peer, 'port', peer_config['port']])
            self.cli_set(base_path + ['cache', peer, 'preference', peer_config['preference']])

        # check validate() - preferences must be unique
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()


if __name__ == '__main__':
    # Create OpenSSH keypair used in RPKI tests
    if not os.path.isfile(rpki_ssh_key):
        cmd(f'ssh-keygen -t rsa -f {rpki_ssh_key} -N ""')

    if not os.path.isfile(rpki_known_hosts):
        cmd(f'touch {rpki_known_hosts}')

    unittest.main(verbosity=2)
