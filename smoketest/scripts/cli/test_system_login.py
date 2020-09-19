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
import platform
import unittest

from platform import release as kernel_version
from subprocess import Popen, PIPE

from vyos.configsession import ConfigSession
from vyos.util import cmd
from vyos.util import read_file

base_path = ['system', 'login']
users = ['vyos1', 'vyos2']

class TestSystemLogin(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())

    def tearDown(self):
        # Delete individual users from configuration
        for user in users:
            self.session.delete(base_path + ['user', user])

        self.session.commit()
        del self.session

    def test_local_user(self):
        """ Check if user can be created and we can SSH to localhost """
        self.session.set(['service', 'ssh', 'port', '22'])

        for user in users:
            name = "VyOS Roxx " + user
            home_dir = "/tmp/" + user

            self.session.set(base_path + ['user', user, 'authentication', 'plaintext-password', user])
            self.session.set(base_path + ['user', user, 'full-name', 'VyOS Roxx'])
            self.session.set(base_path + ['user', user, 'home-directory', home_dir])

        self.session.commit()

        for user in users:
            cmd = ['su','-', user]
            proc = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            tmp = "{}\nuname -a".format(user)
            proc.stdin.write(tmp.encode())
            proc.stdin.flush()
            (stdout, stderr) = proc.communicate()

            # stdout is something like this:
            # b'Linux vyos 4.19.101-amd64-vyos #1 SMP Sun Feb 2 10:18:07 UTC 2020 x86_64 GNU/Linux\n'
            self.assertTrue(len(stdout) > 40)

    def test_radius_kernel_features(self):
        """ T2886: RADIUS requires some Kernel options to be present """
        kernel = platform.release()
        kernel_config = read_file(f'/boot/config-{kernel}')

        # T2886 - RADIUS authentication - check for statically compiled
        # options (=y)
        for option in ['CONFIG_AUDIT', 'CONFIG_HAVE_ARCH_AUDITSYSCALL',
                       'CONFIG_AUDITSYSCALL', 'CONFIG_AUDIT_WATCH',
                       'CONFIG_AUDIT_TREE', 'CONFIG_AUDIT_ARCH']:
            self.assertIn(f'{option}=y', kernel_config)

    def test_radius_config(self):
        """ Verify generated RADIUS configuration files """

        radius_key = 'VyOSsecretVyOS'
        radius_server = '172.16.100.10'
        radius_source = '127.0.0.1'
        radius_port = '2000'
        radius_timeout = '1'

        self.session.set(base_path + ['radius', 'server', radius_server, 'key', radius_key])
        self.session.set(base_path + ['radius', 'server', radius_server, 'port', radius_port])
        self.session.set(base_path + ['radius', 'server', radius_server, 'timeout', radius_timeout])
        self.session.set(base_path + ['radius', 'source-address', radius_source])

        self.session.commit()

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

if __name__ == '__main__':
    unittest.main()
