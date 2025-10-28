#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.defaults import config_files
from vyos.utils.process import cmd
from vyos.utils.process import is_systemd_service_running
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file
from vyos.utils.file import write_file
from vyos.xml_ref import default_value

PROCESS_NAME = 'sshd'
SSHD_CONF = '/run/sshd/sshd_config'
base_path = ['service', 'ssh']
pki_path = ['pki']

key_rsa = '/etc/ssh/ssh_host_rsa_key'
key_dsa = '/etc/ssh/ssh_host_dsa_key'
key_ed25519 = '/etc/ssh/ssh_host_ed25519_key'
trusted_user_ca = config_files['sshd_user_ca']
test_command = 'uname -a'

def get_config_value(key):
    tmp = read_file(SSHD_CONF)
    tmp = re.findall(f'\n?{key}\s+(.*)', tmp)
    return tmp

trusted_user_ca_path = base_path + ['trusted-user-ca']
# CA and signed user key generated using:
# ssh-keygen -f vyos-ssh-ca.key
# ssh-keygen -f vyos_testca  -C "vyos_tesca@vyos.net"
# ssh-keygen -s vyos-ssh-ca.key -I vyos_testca@vyos.net -n vyos,vyos_testca -V +520w vyos_testca.pub
ca_cert_data = """
AAAAB3NzaC1yc2EAAAADAQABAAABgQCTBa7+TTefsMLTHuuLPUmmm7SGAuoK03oZEIi2/O
sww1uhCdKrm7bFvSUFpWvq3gX8TSS+yO5kNKz3BTMBu7oq01/Ewjyw0jR+fUog76x7mCzd
2iI4QmPj4lNHSUFquaELt2aBwY4f7LtjxRCCgtWgirq/Qk+P27uJKErvndyYc95v9no15z
lQFSdUid6tF8IjYljK8pXP0JshFp3XnFV2Rg80j7O66mRtVFC4tt2vluyIFeIID+5fL03v
LXbT/2zNdoH6QiI9NGWkxhS7zFYziVd/rzG5xlEB1ezs2Sz4zjMPgV3GiMINb6tjEWNJhM
KtDWIt+3UDpx+2T9PrhDBDFMlneiHCD6MxRv2sLbicevSj0PV7/fRnwoHs6hDKCU5eS2Mc
CTxXr4jaboLZ6q3sbGHCHZo/PuA8Sl9iZCM4GCxx5bgvRRmGpgZv4PfFzA2b/wTHkKnf6E
kuthoAJufmNxPaZQRQKF34SdmTKgSJTCY1gqwCH2iNg0PVKU+vN8c=
"""

cert_user_key = """-----BEGIN OPENSSH PRIVATE KEY-----
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
-----END OPENSSH PRIVATE KEY-----
"""

cert_user_signed = """
ssh-rsa-cert-v01@openssh.com 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 vyos_tesca@vyos.net
"""

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
        # always forward to base class
        super().tearDown()

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
        self.assertTrue('1234' in port)

        # Check DNS usage
        dns = get_config_value('UseDNS')[0]
        self.assertTrue('no' in dns)

        # Check PasswordAuthentication
        pwd = get_config_value('PasswordAuthentication')[0]
        self.assertTrue('no' in pwd)

        # Check loglevel
        loglevel = get_config_value('LogLevel')[0]
        self.assertTrue('VERBOSE' in loglevel)

        # Check listen address
        address = get_config_value('ListenAddress')[0]
        self.assertTrue('127.0.0.1' in address)

        # Check keepalive
        keepalive = get_config_value('ClientAliveInterval')[0]
        self.assertTrue('100' in keepalive)

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

        self.cli_set(base_path)
        self.cli_set(['system', 'login', 'user', test_user, 'authentication',
                      'plaintext-password', test_pass])

        # commit changes
        self.cli_commit()

        # Login with proper credentials
        output, error = self.ssh_send_cmd(test_command, test_user, test_pass)
        # verify login
        self.assertFalse(error)
        self.assertEqual(output, cmd(test_command))

        # Login with invalid credentials
        with self.assertRaises(paramiko.ssh_exception.AuthenticationException):
            output, error = self.ssh_send_cmd(test_command, 'invalid_user',
                                              'invalid_password')

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
            f'DETECTION_TIME={detect_time}',
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
        kexes = [
            'diffie-hellman-group14-sha1',
            'ecdh-sha2-nistp256',
            'ecdh-sha2-nistp384',
            'ecdh-sha2-nistp521',
        ]
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

        ssh_lines = [
            'Ciphers aes128-cbc,aes128-ctr,aes256-cbc,aes256-ctr',
            'HostKeyAlgorithms sk-ssh-ed25519@openssh.com,ssh-rsa,ssh-ed25519',
            'MACs hmac-sha1,hmac-sha2-256,hmac-sha2-512',
            'KexAlgorithms diffie-hellman-group14-sha1,ecdh-sha2-nistp256,ecdh-sha2-nistp384,ecdh-sha2-nistp521',
            'RekeyLimit 1024M 60M',
        ]
        tmp_sshd_conf = read_file(SSHD_CONF)

        for line in ssh_lines:
            self.assertIn(line, tmp_sshd_conf)

    def test_ssh_pubkey_accepted_algorithm(self):
        algs = [
            'ssh-ed25519',
            'ecdsa-sha2-nistp256',
            'ecdsa-sha2-nistp384',
            'ecdsa-sha2-nistp521',
            'ssh-dss',
            'ssh-rsa',
            'rsa-sha2-256',
            'rsa-sha2-512',
        ]

        expected = 'PubkeyAcceptedAlgorithms '
        for alg in algs:
            self.cli_set(base_path + ['pubkey-accepted-algorithm', alg])
            expected = f'{expected}{alg},'
        expected = expected[:-1]

        self.cli_commit()
        tmp_sshd_conf = read_file(SSHD_CONF)
        self.assertIn(expected, tmp_sshd_conf)

    def test_ssh_trusted_user_ca(self):
        ca_cert_name = 'test_ca'
        public_key_type = 'ssh-rsa'
        public_key_data = ca_cert_data.replace('\n', '')
        test_user = 'vyos_testca'
        principal = 'vyos'
        user_auth_base = ['system', 'login', 'user', test_user]

        # create user account
        self.cli_set(user_auth_base)
        self.cli_set(pki_path + ['openssh', ca_cert_name, 'public',
                                 'key', public_key_data])
        self.cli_set(pki_path + ['openssh', ca_cert_name, 'public',
                                 'type', public_key_type])
        self.cli_set(trusted_user_ca_path, value=ca_cert_name)
        self.cli_commit()

        trusted_user_ca_config = get_config_value('TrustedUserCAKeys')
        self.assertIn(trusted_user_ca, trusted_user_ca_config)

        authorize_principals_file_config = get_config_value('AuthorizedPrincipalsFile')
        self.assertIn('none', authorize_principals_file_config)

        ca_key_contents = read_file(trusted_user_ca).lstrip().rstrip()
        self.assertIn(f'{public_key_type} {public_key_data}', ca_key_contents)

        # Verify functionality by logging into the system using signed user key
        key_filename = f'/tmp/{test_user}'
        write_file(key_filename, cert_user_key, mode=0o600)
        write_file(f'{key_filename}-cert.pub', cert_user_signed.replace('\n', ''))

        # Login with proper credentials
        output, error = self.ssh_send_cmd(test_command, test_user, password=None,
                                          key_filename=key_filename)
        # Verify login
        self.assertFalse(error)
        self.assertEqual(output, cmd(test_command))

        # Enable user principal name - logins only allowed if certificate contains
        # said principal name
        self.cli_set(user_auth_base + ['authentication', 'principal', principal])
        self.cli_commit()

        # Verify generated SSH principals
        authorized_principals_file = f'/home/{test_user}/.ssh/authorized_principals'
        authorized_principals = read_file(authorized_principals_file, sudo=True)
        self.assertIn(principal, authorized_principals)

        # Login with proper credentials
        output, error = self.ssh_send_cmd(test_command, test_user, password=None,
                                          key_filename=key_filename)
        # Verify login
        self.assertFalse(error)
        self.assertEqual(output, cmd(test_command))

        self.cli_delete(trusted_user_ca_path)
        self.cli_delete(user_auth_base)
        self.cli_delete(['pki', 'ca', ca_cert_name])
        self.cli_commit()

        # Verify the CA key is removed
        trusted_user_ca_config = get_config_value('TrustedUserCAKeys')
        self.assertNotIn(trusted_user_ca, trusted_user_ca_config)
        self.assertFalse(os.path.exists(trusted_user_ca))

        authorize_principals_file_config = get_config_value('AuthorizedPrincipalsFile')
        self.assertNotIn('none', authorize_principals_file_config)
        self.assertFalse(os.path.exists(f'/home/{test_user}/.ssh/authorized_principals'))

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
