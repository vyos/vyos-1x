#!/usr/bin/env python3
#
# Copyright (C) 2019-2024 VyOS maintainers and contributors
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
import paramiko
import re
import unittest

from pwd import getpwall

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.process import cmd
from vyos.utils.process import is_systemd_service_running
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file
from vyos.xml_ref import default_value

PROCESS_NAME = 'sshd'
SSHD_CONF = '/run/sshd/sshd_config'
base_path = ['service', 'ssh']

key_rsa = '/etc/ssh/ssh_host_rsa_key'
key_dsa = '/etc/ssh/ssh_host_dsa_key'
key_ed25519 = '/etc/ssh/ssh_host_ed25519_key'

def get_config_value(key):
    tmp = read_file(SSHD_CONF)
    tmp = re.findall(f'\n?{key}\s+(.*)', tmp)
    return tmp

class TestServiceSSH(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestServiceSSH, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)
        cls.cli_delete(cls, ['vrf'])

    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        # delete testing SSH config
        self.cli_delete(base_path)
        self.cli_delete(['vrf'])
        self.cli_commit()

        self.assertTrue(os.path.isfile(key_rsa))
        self.assertTrue(os.path.isfile(key_dsa))
        self.assertTrue(os.path.isfile(key_ed25519))

        # Established SSH connections remains running after service is stopped.
        # We can not use process_named_running here - we rather need to check
        # that the systemd service is no longer running
        self.assertFalse(is_systemd_service_running(PROCESS_NAME))

    def test_ssh_default(self):
        # Check if SSH service runs with default settings - used for checking
        # behavior of <defaultValue> in XML definition
        self.cli_set(base_path)

        # commit changes
        self.cli_commit()

        # Check configured port agains CLI default value
        port = get_config_value('Port')
        cli_default = default_value(base_path + ['port'])
        self.assertEqual(port, cli_default)

    def test_ssh_single_listen_address(self):
        # Check if SSH service can be configured and runs
        self.cli_set(base_path + ['port', '1234'])
        self.cli_set(base_path + ['disable-host-validation'])
        self.cli_set(base_path + ['disable-password-authentication'])
        self.cli_set(base_path + ['loglevel', 'verbose'])
        self.cli_set(base_path + ['client-keepalive-interval', '100'])
        self.cli_set(base_path + ['listen-address', '127.0.0.1'])

        # commit changes
        self.cli_commit()

        # Check configured port
        port = get_config_value('Port')[0]
        self.assertTrue("1234" in port)

        # Check DNS usage
        dns = get_config_value('UseDNS')[0]
        self.assertTrue("no" in dns)

        # Check PasswordAuthentication
        pwd = get_config_value('PasswordAuthentication')[0]
        self.assertTrue("no" in pwd)

        # Check loglevel
        loglevel = get_config_value('LogLevel')[0]
        self.assertTrue("VERBOSE" in loglevel)

        # Check listen address
        address = get_config_value('ListenAddress')[0]
        self.assertTrue("127.0.0.1" in address)

        # Check keepalive
        keepalive = get_config_value('ClientAliveInterval')[0]
        self.assertTrue("100" in keepalive)

    def test_ssh_multiple_listen_addresses(self):
        # Check if SSH service can be configured and runs with multiple
        # listen ports and listen-addresses
        ports = ['22', '2222', '2223', '2224']
        for port in ports:
            self.cli_set(base_path + ['port', port])

        addresses = ['127.0.0.1', '::1']
        for address in addresses:
            self.cli_set(base_path + ['listen-address', address])

        # commit changes
        self.cli_commit()

        # Check configured port
        tmp = get_config_value('Port')
        for port in ports:
            self.assertIn(port, tmp)

        # Check listen address
        tmp = get_config_value('ListenAddress')
        for address in addresses:
            self.assertIn(address, tmp)

    def test_ssh_vrf_single(self):
        vrf = 'mgmt'
        # Check if SSH service can be bound to given VRF
        self.cli_set(base_path + ['vrf', vrf])

        # VRF does yet not exist - an error must be thrown
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(['vrf', 'name', vrf, 'table', '1338'])

        # commit changes
        self.cli_commit()

        # Check for process in VRF
        tmp = cmd(f'ip vrf pids {vrf}')
        self.assertIn(PROCESS_NAME, tmp)

    def test_ssh_vrf_multi(self):
        # Check if SSH service can be bound to multiple VRFs
        vrfs = ['red', 'blue', 'green']
        for vrf in vrfs:
            self.cli_set(base_path + ['vrf', vrf])

        # VRF does yet not exist - an error must be thrown
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        table = 12345
        for vrf in vrfs:
            self.cli_set(['vrf', 'name', vrf, 'table', str(table)])
            table += 1

        # commit changes
        self.cli_commit()

        # Check for process in VRF
        for vrf in vrfs:
            tmp = cmd(f'ip vrf pids {vrf}')
            self.assertIn(PROCESS_NAME, tmp)

    def test_ssh_login(self):
        # Perform SSH login and command execution with a predefined user. The
        # result (output of uname -a) must match the output if the command is
        # run natively.
        #
        # We also try to login as an invalid user - this is not allowed to work.

        test_user = 'ssh_test'
        test_pass = 'v2i57DZs8idUwMN3VC92'
        test_command = 'uname -a'

        self.cli_set(base_path)
        self.cli_set(['system', 'login', 'user', test_user, 'authentication', 'plaintext-password', test_pass])

        # commit changes
        self.cli_commit()

        # Login with proper credentials
        output, error = self.ssh_send_cmd(test_command, test_user, test_pass)
        # verify login
        self.assertFalse(error)
        self.assertEqual(output, cmd(test_command))

        # Login with invalid credentials
        with self.assertRaises(paramiko.ssh_exception.AuthenticationException):
            output, error = self.ssh_send_cmd(test_command, 'invalid_user', 'invalid_password')

        self.cli_delete(['system', 'login', 'user', test_user])
        self.cli_commit()

        # After deletion the test user is not allowed to remain in /etc/passwd
        usernames = [x[0] for x in getpwall()]
        self.assertNotIn(test_user, usernames)

    def test_ssh_dynamic_protection(self):
        # check sshguard service

        SSHGUARD_CONFIG = '/etc/sshguard/sshguard.conf'
        SSHGUARD_WHITELIST = '/etc/sshguard/whitelist'
        SSHGUARD_PROCESS = 'sshguard'
        block_time = '123'
        detect_time = '1804'
        port = '22'
        threshold = '10'
        allow_list = ['192.0.2.0/24', '2001:db8::/48']

        self.cli_set(base_path + ['dynamic-protection', 'block-time', block_time])
        self.cli_set(base_path + ['dynamic-protection', 'detect-time', detect_time])
        self.cli_set(base_path + ['dynamic-protection', 'threshold', threshold])
        for allow in allow_list:
            self.cli_set(base_path + ['dynamic-protection', 'allow-from', allow])

        # commit changes
        self.cli_commit()

        # Check configured port
        tmp = get_config_value('Port')
        self.assertIn(port, tmp)

        # Check sshgurad service
        self.assertTrue(process_named_running(SSHGUARD_PROCESS))

        sshguard_lines = [
            f'THRESHOLD={threshold}',
            f'BLOCK_TIME={block_time}',
            f'DETECTION_TIME={detect_time}'
        ]

        tmp_sshguard_conf = read_file(SSHGUARD_CONFIG)
        for line in sshguard_lines:
            self.assertIn(line, tmp_sshguard_conf)

        tmp_whitelist_conf = read_file(SSHGUARD_WHITELIST)
        for allow in allow_list:
            self.assertIn(allow, tmp_whitelist_conf)

        # Delete service ssh dynamic-protection
        # but not service ssh itself
        self.cli_delete(base_path + ['dynamic-protection'])
        self.cli_commit()

        self.assertFalse(process_named_running(SSHGUARD_PROCESS))


    # Network Device Collaborative Protection Profile
    def test_ssh_ndcpp(self):
        ciphers = ['aes128-cbc', 'aes128-ctr', 'aes256-cbc', 'aes256-ctr']
        host_key_algs = ['sk-ssh-ed25519@openssh.com', 'ssh-rsa', 'ssh-ed25519']
        kexes = ['diffie-hellman-group14-sha1', 'ecdh-sha2-nistp256', 'ecdh-sha2-nistp384', 'ecdh-sha2-nistp521']
        macs = ['hmac-sha1', 'hmac-sha2-256', 'hmac-sha2-512']
        rekey_time = '60'
        rekey_data = '1024'

        for cipher in ciphers:
            self.cli_set(base_path + ['ciphers', cipher])
        for host_key in host_key_algs:
            self.cli_set(base_path + ['hostkey-algorithm', host_key])
        for kex in kexes:
            self.cli_set(base_path + ['key-exchange', kex])
        for mac in macs:
            self.cli_set(base_path + ['mac', mac])
        # Optional rekey parameters
        self.cli_set(base_path + ['rekey', 'data', rekey_data])
        self.cli_set(base_path + ['rekey', 'time', rekey_time])

        # commit changes
        self.cli_commit()

        ssh_lines = ['Ciphers aes128-cbc,aes128-ctr,aes256-cbc,aes256-ctr',
                     'HostKeyAlgorithms sk-ssh-ed25519@openssh.com,ssh-rsa,ssh-ed25519',
                     'MACs hmac-sha1,hmac-sha2-256,hmac-sha2-512',
                     'KexAlgorithms diffie-hellman-group14-sha1,ecdh-sha2-nistp256,ecdh-sha2-nistp384,ecdh-sha2-nistp521',
                     'RekeyLimit 1024M 60M'
                     ]
        tmp_sshd_conf = read_file(SSHD_CONF)

        for line in ssh_lines:
            self.assertIn(line, tmp_sshd_conf)

    def test_ssh_pubkey_accepted_algorithm(self):
        algs = ['ssh-ed25519', 'ecdsa-sha2-nistp256', 'ecdsa-sha2-nistp384',
                'ecdsa-sha2-nistp521', 'ssh-dss', 'ssh-rsa', 'rsa-sha2-256',
                'rsa-sha2-512'
                ]

        expected = 'PubkeyAcceptedAlgorithms '
        for alg in algs:
            self.cli_set(base_path + ['pubkey-accepted-algorithm', alg])
            expected = f'{expected}{alg},'
        expected = expected[:-1]

        self.cli_commit()
        tmp_sshd_conf = read_file(SSHD_CONF)
        self.assertIn(expected, tmp_sshd_conf)


if __name__ == '__main__':
    unittest.main(verbosity=2)
