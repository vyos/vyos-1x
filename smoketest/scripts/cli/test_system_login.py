#!/usr/bin/env python3
#
# Copyright (C) 2019-2025 VyOS maintainers and contributors
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
import jinja2
import secrets
import string
import paramiko
import shutil

from base_vyostest_shim import VyOSUnitTestSHIM

from gzip import GzipFile
from subprocess import Popen
from subprocess import PIPE
from pwd import getpwall

from vyos.configsession import ConfigSessionError
from vyos.utils.auth import get_current_user
from vyos.utils.process import cmd
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file
from vyos.utils.file import write_file
from vyos.template import inc_ip

base_path = ['system', 'login']
users = ['vyos1', 'vyos-roxx123', 'VyOS-123_super.Nice']

SSH_PROCESS_NAME = 'sshd'

ssh_pubkey = """
AAAAB3NzaC1yc2EAAAADAQABAAABgQD0NuhUOEtMIKnUVFIHoFatqX/c4mjerXyF
TlXYfVt6Ls2NZZsUSwHbnhK4BKDrPvVZMW/LycjQPzWW6TGtk6UbZP1WqdviQ9hP
jsEeKJSTKciMSvQpjBWyEQQPXSKYQC7ryQQilZDqnJgzqwzejKEe+nhhOdBvjuZc
uukxjT69E0UmWAwLxzvfiurwiQaC7tG+PwqvtfHOPL3i6yRO2C5ORpFarx8PeGDS
IfIXJCr3LoUbLHeuE7T2KaOKQcX0UsWJ4CoCapRLpTVYPDB32BYfgq7cW1Sal1re
EGH2PzuXBklinTBgCHA87lHjpwDIAqdmvMj7SXIW9LxazLtP+e37sexE7xEs0cpN
l68txdDbY2P2Kbz5mqGFfCvBYKv9V2clM5vyWNy/Xp5TsCis89nn83KJmgFS7sMx
pHJz8umqkxy3hfw0K7BRFtjWd63sbOP8Q/SDV7LPaIfIxenA9zv2rY7y+AIqTmSr
TTSb0X1zPGxPIRFy5GoGtO9Mm5h4OZk=
"""

tac_image = 'docker.io/lfkeitel/tacacs_plus:alpine'
tac_image_path = '/usr/share/vyos/tacplus-alpine.tar'

TAC_PLUS_TMPL_SRC = """
id = spawnd {
    debug redirect = /dev/stdout
    listen = { port = 49 }
    spawn = {
        instances min = 1
        instances max = 10
    }
    background = no
}

id = tac_plus {
    debug = ALL
    log = stdout {
        destination = /dev/stdout
    }
    authorization log group = yes
    authentication log = stdout
    authorization log = stdout
    accounting log = stdout

    host = smoketest {
        address = {{ source_address }}/32
        enable = clear enable
        key = {{ tacacs_secret }}
    }

    group = admin {
        default service = permit
        enable = permit
        service = shell {
            default command = permit
            default attribute = permit
            set priv-lvl = 15
        }
    }

    user = {{ username }} {
        password = clear {{ password }}
        member = admin
    }
}
"""

class TestSystemLogin(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSystemLogin, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration which will break this test
        cls.cli_delete(cls, base_path + ['radius'])
        cls.cli_delete(cls, base_path + ['tacacs'])

        # Load image for smoketest provided in vyos-1x-smoketest
        if not os.path.exists(tac_image_path):
            cls.fail(cls, f'{tac_image} image not available')
        cmd(f'sudo podman load -i {tac_image_path}')

    @classmethod
    def tearDownClass(cls):
        super(TestSystemLogin, cls).tearDownClass()
        # Cleanup podman image
        cmd(f'sudo podman image rm -f {tac_image}')

    def tearDown(self):
        # Delete individual users from configuration
        for user in users:
            self.cli_delete(base_path + ['user', user])

        self.cli_delete(base_path + ['radius'])
        self.cli_delete(base_path + ['tacacs'])

        self.cli_commit()

        # After deletion, a user is not allowed to remain in /etc/passwd
        usernames = [x[0] for x in getpwall()]
        for user in users:
            self.assertNotIn(user, usernames)

    def test_add_linux_system_user(self):
        # We are not allowed to re-use a username already taken by the Linux
        # base system
        system_user = 'backup'
        self.cli_set(base_path + ['user', system_user, 'authentication', 'plaintext-password', system_user])

        # check validate() - can not add username which exists on the Debian
        # base system (UID < 1000)
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(base_path + ['user', system_user])

    def test_system_login_user(self):
        # Check if user can be created and we can SSH to localhost
        self.cli_set(['service', 'ssh', 'port', '22'])

        for user in users:
            name = f'VyOS Roxx {user}'
            home_dir = f'/tmp/smoketest/{user}'

            self.cli_set(base_path + ['user', user, 'authentication', 'plaintext-password', user])
            self.cli_set(base_path + ['user', user, 'full-name', name])
            self.cli_set(base_path + ['user', user, 'home-directory', home_dir])

        self.cli_commit()

        for user in users:
            tmp = ['su','-', user]
            proc = Popen(tmp, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            tmp = f'{user}\nuname -a'
            proc.stdin.write(tmp.encode())
            proc.stdin.flush()
            (stdout, stderr) = proc.communicate()

            # stdout is something like this:
            # b'Linux vyos 6.6.66-vyos 6.6.66-vyos #1 SMP Mon Dec 30 19:05:15 UTC 2024 x86_64 GNU/Linux\n'
            self.assertTrue(len(stdout) > 40)

        locked_user = users[0]
        # disable the first user in list
        self.cli_set(base_path + ['user', locked_user, 'disable'])
        self.cli_commit()
        # check if account is locked
        tmp = cmd(f'sudo passwd -S {locked_user}')
        self.assertIn(f'{locked_user} L ', tmp)

        # unlock account
        self.cli_delete(base_path + ['user', locked_user, 'disable'])
        self.cli_commit()
        # check if account is unlocked
        tmp = cmd(f'sudo passwd -S {locked_user}')
        self.assertIn(f'{locked_user} P ', tmp)

    def test_system_login_otp(self):
        otp_user = 'otp-test_user'
        otp_password = 'SuperTestPassword'
        otp_key = '76A3ZS6HFHBTOK2H4NDHTIVFPQ'

        self.cli_set(base_path + ['user', otp_user, 'authentication', 'plaintext-password', otp_password])
        self.cli_set(base_path + ['user', otp_user, 'authentication', 'otp', 'key', otp_key])

        self.cli_commit()

        # Check if OTP key was written properly
        tmp = cmd(f'sudo head -1 /home/{otp_user}/.google_authenticator')
        self.assertIn(otp_key, tmp)

        self.cli_delete(base_path + ['user', otp_user])

    def test_system_user_ssh_key(self):
        ssh_user = 'ssh-test_user'
        public_keys = 'vyos_test@domain-foo.com'
        type = 'ssh-rsa'

        self.cli_set(base_path + ['user', ssh_user, 'authentication', 'public-keys', public_keys, 'key', ssh_pubkey.replace('\n','')])

        # check validate() - missing type for public-key
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['user', ssh_user, 'authentication', 'public-keys', public_keys, 'type', type])

        self.cli_commit()

        # Check that SSH key was written properly
        tmp = cmd(f'sudo cat /home/{ssh_user}/.ssh/authorized_keys')
        key = f'{type} ' + ssh_pubkey.replace('\n','')
        self.assertIn(key, tmp)

        self.cli_delete(base_path + ['user', ssh_user])

    def test_radius_kernel_features(self):
        # T2886: RADIUS requires some Kernel options to be present
        kernel_config = GzipFile('/proc/config.gz').read().decode('UTF-8')

        # T2886 - RADIUS authentication - check for statically compiled options
        options = ['CONFIG_AUDIT', 'CONFIG_AUDITSYSCALL', 'CONFIG_AUDIT_ARCH']

        for option in options:
            self.assertIn(f'{option}=y', kernel_config)

    def test_system_login_radius_ipv4(self):
        # Verify generated RADIUS configuration files

        radius_key = 'VyOSsecretVyOS'
        radius_server = '172.16.100.10'
        radius_source = '127.0.0.1'
        radius_port = '2000'
        radius_timeout = '1'

        self.cli_set(base_path + ['radius', 'server', radius_server, 'key', radius_key])
        self.cli_set(base_path + ['radius', 'server', radius_server, 'port', radius_port])
        self.cli_set(base_path + ['radius', 'server', radius_server, 'timeout', radius_timeout])
        self.cli_set(base_path + ['radius', 'source-address', radius_source])
        self.cli_set(base_path + ['radius', 'source-address', inc_ip(radius_source, 1)])

        # check validate() - Only one IPv4 source-address supported
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['radius', 'source-address', inc_ip(radius_source, 1)])

        self.cli_commit()

        # this file must be read with higher permissions
        pam_radius_auth_conf = cmd('sudo cat /etc/pam_radius_auth.conf')
        tmp = re.findall(r'\n?{}:{}\s+{}\s+{}\s+{}'.format(radius_server,
                        radius_port, radius_key, radius_timeout,
                        radius_source), pam_radius_auth_conf)
        self.assertTrue(tmp)

        # required, static options
        self.assertIn('priv-lvl 15', pam_radius_auth_conf)
        self.assertIn('mapped_priv_user radius_priv_user', pam_radius_auth_conf)

        # PAM
        pam_common_account = read_file('/etc/pam.d/common-account')
        self.assertIn('pam_radius_auth.so', pam_common_account)

        pam_common_auth = read_file('/etc/pam.d/common-auth')
        self.assertIn('pam_radius_auth.so', pam_common_auth)

        pam_common_session = read_file('/etc/pam.d/common-session')
        self.assertIn('pam_radius_auth.so', pam_common_session)

        pam_common_session_noninteractive = read_file('/etc/pam.d/common-session-noninteractive')
        self.assertIn('pam_radius_auth.so', pam_common_session_noninteractive)

        # NSS
        nsswitch_conf = read_file('/etc/nsswitch.conf')
        tmp = re.findall(r'passwd:\s+mapuid\s+files\s+mapname', nsswitch_conf)
        self.assertTrue(tmp)

        tmp = re.findall(r'group:\s+mapname\s+files', nsswitch_conf)
        self.assertTrue(tmp)

    def test_system_login_radius_ipv6(self):
        # Verify generated RADIUS configuration files

        radius_key = 'VyOS-VyOS'
        radius_server = '2001:db8::1'
        radius_source = '::1'
        radius_port = '4000'
        radius_timeout = '4'

        self.cli_set(base_path + ['radius', 'server', radius_server, 'key', radius_key])
        self.cli_set(base_path + ['radius', 'server', radius_server, 'port', radius_port])
        self.cli_set(base_path + ['radius', 'server', radius_server, 'timeout', radius_timeout])
        self.cli_set(base_path + ['radius', 'source-address', radius_source])
        self.cli_set(base_path + ['radius', 'source-address', inc_ip(radius_source, 1)])

        # check validate() - Only one IPv4 source-address supported
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['radius', 'source-address', inc_ip(radius_source, 1)])

        self.cli_commit()

        # this file must be read with higher permissions
        pam_radius_auth_conf = cmd('sudo cat /etc/pam_radius_auth.conf')
        tmp = re.findall(r'\n?\[{}\]:{}\s+{}\s+{}\s+\[{}\]'.format(radius_server,
                        radius_port, radius_key, radius_timeout,
                        radius_source), pam_radius_auth_conf)
        self.assertTrue(tmp)

        # required, static options
        self.assertIn('priv-lvl 15', pam_radius_auth_conf)
        self.assertIn('mapped_priv_user radius_priv_user', pam_radius_auth_conf)

        # PAM
        pam_common_account = read_file('/etc/pam.d/common-account')
        self.assertIn('pam_radius_auth.so', pam_common_account)

        pam_common_auth = read_file('/etc/pam.d/common-auth')
        self.assertIn('pam_radius_auth.so', pam_common_auth)

        pam_common_session = read_file('/etc/pam.d/common-session')
        self.assertIn('pam_radius_auth.so', pam_common_session)

        pam_common_session_noninteractive = read_file('/etc/pam.d/common-session-noninteractive')
        self.assertIn('pam_radius_auth.so', pam_common_session_noninteractive)

        # NSS
        nsswitch_conf = read_file('/etc/nsswitch.conf')
        tmp = re.findall(r'passwd:\s+mapuid\s+files\s+mapname', nsswitch_conf)
        self.assertTrue(tmp)

        tmp = re.findall(r'group:\s+mapname\s+files', nsswitch_conf)
        self.assertTrue(tmp)

    def test_system_login_max_login_session(self):
        max_logins = '2'
        timeout = '600'

        self.cli_set(base_path + ['max-login-session', max_logins])

        # 'max-login-session' must be only with 'timeout' option
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['timeout', timeout])

        self.cli_commit()

        security_limits = read_file('/etc/security/limits.d/10-vyos.conf')
        self.assertIn(f'* - maxsyslogins {max_logins}', security_limits)

        self.cli_delete(base_path + ['timeout'])
        self.cli_delete(base_path + ['max-login-session'])

    def test_system_login_tacacs(self):
        tacacs_secret = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))
        tacacs_servers = ['100.64.0.11', '100.64.0.12']
        source_address = '100.64.0.1'
        dummy_if = 'dum12759'

        # Load container image for lac_plus daemon
        tac_plus_config = '/tmp/smoketest-tacacs-server'
        tac_container_path = ['container', 'name', 'tacacs-1']

        # Generate random string with 10 digits
        username = 'tactest'
        password = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))
        tac_test_user = {
            'username' : username,
            'password' : password,
            'tacacs_secret' : tacacs_secret,
            'source_address' : source_address,
        }

        tmpl = jinja2.Template(TAC_PLUS_TMPL_SRC)
        write_file(f'{tac_plus_config}/tac_plus.cfg', tmpl.render(tac_test_user))

        # Check if SSH service is running
        ssh_running = process_named_running(SSH_PROCESS_NAME)
        if not ssh_running:
            # Start SSH service
            self.cli_set(['service', 'ssh'])

        # Start tac_plus container
        self.cli_set(tac_container_path + ['allow-host-networks'])
        self.cli_set(tac_container_path + ['image', tac_image])
        self.cli_set(tac_container_path + ['volume', 'config', 'destination', '/etc/tac_plus'])
        self.cli_set(tac_container_path + ['volume', 'config', 'mode', 'ro'])
        self.cli_set(tac_container_path + ['volume', 'config', 'source', tac_plus_config])

        # Start container
        self.cli_commit()

        # Define TACACS traffic source address
        self.cli_set(['interfaces', 'dummy', dummy_if, 'address', f'{source_address}/32'])
        self.cli_set(base_path + ['tacacs', 'source-address', source_address])

        # Define TACACS servers
        for server in tacacs_servers:
            # Use this system as "remote" TACACS server
            self.cli_set(['interfaces', 'dummy', dummy_if, 'address', f'{server}/32'])
            self.cli_set(base_path + ['tacacs', 'server', server, 'key', tacacs_secret])

        self.cli_commit()

        # NSS
        nsswitch_conf = read_file('/etc/nsswitch.conf')
        tmp = re.findall(r'passwd:\s+tacplus\s+files', nsswitch_conf)
        self.assertTrue(tmp)

        tmp = re.findall(r'group:\s+tacplus\s+files', nsswitch_conf)
        self.assertTrue(tmp)

        # PAM TACACS configuration
        pam_tacacs_conf = read_file('/etc/tacplus_servers')
        # NSS TACACS configuration
        nss_tacacs_conf = read_file('/etc/tacplus_nss.conf')
        # Users have individual home directories
        self.assertIn('user_homedir=1', pam_tacacs_conf)

        # specify services
        self.assertIn('service=shell', pam_tacacs_conf)
        self.assertIn('protocol=ssh', pam_tacacs_conf)

        # Verify configured TACACS source address
        self.assertIn(f'source_ip={source_address}', pam_tacacs_conf)
        self.assertIn(f'source_ip={source_address}', nss_tacacs_conf)

        # Verify configured TACACS servers
        for server in tacacs_servers:
            self.assertIn(f'secret={tacacs_secret}', pam_tacacs_conf)
            self.assertIn(f'server={server}', pam_tacacs_conf)

            self.assertIn(f'secret={tacacs_secret}', nss_tacacs_conf)
            self.assertIn(f'server={server}', nss_tacacs_conf)

        # Login with proper credentials
        test_command = 'uname -a'
        out, err = self.ssh_send_cmd(test_command, username, password)
        # verify login
        self.assertFalse(err)
        self.assertEqual(out, cmd(test_command))

        # Login with invalid credentials
        with self.assertRaises(paramiko.ssh_exception.AuthenticationException):
            _, _ = self.ssh_send_cmd(test_command, username, f'{password}1')

        # Remove TACACS configuration
        self.cli_delete(base_path + ['tacacs'])
        # Remove tac_plus container
        self.cli_delete(tac_container_path)
        # Remove dummy interface
        self.cli_delete(['interfaces', 'dummy', dummy_if])
        self.cli_commit()

        # Remove rendered tac_plus daemon configuration
        shutil.rmtree(tac_plus_config)

        # Stop SSH service if it was not running before
        if not ssh_running:
            self.cli_delete(['service', 'ssh'])

    def test_delete_current_user(self):
        current_user = get_current_user()

        # We are not allowed to delete the current user
        self.cli_delete(base_path + ['user', current_user])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_discard()

if __name__ == '__main__':
    unittest.main(verbosity=2)
