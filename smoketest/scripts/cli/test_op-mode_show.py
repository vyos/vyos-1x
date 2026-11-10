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
import stat
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import cmdl
from vyos.version import get_version

base_path = ['show']

class TestOPModeShow(VyOSUnitTestSHIM.TestCase):
    def test_op_mode_show_version(self):
        # Retrieve output of "show version" OP-mode command
        tmp = self.op_mode(base_path + ['version'])
        # Validate
        version = get_version()
        self.assertIn(f'Version:          VyOS {version}', tmp)

    def test_op_mode_show_version_kernel(self):
        # Retrieve output of "show version" OP-mode command
        tmp = self.op_mode(base_path + ['version', 'kernel'])
        self.assertEqual(cmdl(['uname', '-r']), tmp)

    def test_op_mode_show_vrf(self):
        # Retrieve output of "show version" OP-mode command
        tmp = self.op_mode(base_path + ['vrf'])
        # Validate
        self.assertIn('VRF is not configured', tmp)

    def test_op_mode_operator_user(self):
        login_path = ['system', 'login']
        op_wrapper = '/opt/vyatta/bin/vyatta-op-cmd-wrapper'
        op_runner = '/usr/bin/vyos-op-run'
        op_group = 'smoketest'
        op_user = 'smoketest-operator'
        op_password = 'vyos-operator-123'

        # T9587: operators do not use sudo, they rely on the SUID bit of the
        # op-mode runner to gain privileges after the permission check
        self.assertTrue(os.stat(op_runner).st_mode & stat.S_ISUID)

        # The SSH helper uses password login on localhost:22, an existing SSH
        # configuration must permit that
        config = ConfigTreeQuery()
        ssh_path = ['service', 'ssh']
        ssh_pre_test = config.exists(ssh_path)
        if ssh_pre_test:
            listen = config.values(ssh_path + ['listen-address'])
            if ('22' not in (config.values(ssh_path + ['port']) or ['22']) or
                (listen and not {'0.0.0.0', '::', '127.0.0.1', '::1'} & set(listen)) or
                config.exists(ssh_path + ['disable-password-authentication']) or
                config.exists(ssh_path + ['vrf'])):
                self.skipTest('SSH configuration does not permit password login on localhost:22')
        else:
            self.cli_set(ssh_path)

        # A policy entry implicitly allows all of its sub-commands, while a
        # more specific entry rejects the shorter command
        allowed = ['show version kernel', 'show interfaces']
        denied = ['show version', 'show version frr']

        for command in allowed:
            self.cli_set(login_path + ['operator-group', op_group,
                                       'command-policy', 'allow', command])
        self.cli_set(login_path + ['user', op_user, 'authentication',
                                   'plaintext-password', op_password])
        self.cli_set(login_path + ['user', op_user, 'operator', 'group', op_group])
        self.cli_commit()

        try:
            for command in allowed:
                out, err = self.ssh_send_cmd(f'{op_wrapper} {command}',
                                             op_user, op_password)
                self.assertFalse(err)
                self.assertEqual(out, self.op_mode([command]))

            for command in denied:
                out, err = self.ssh_send_cmd(f'{op_wrapper} {command}',
                                             op_user, op_password)
                self.assertFalse(out)
                self.assertIn('You do not have a permission to execute VyOS command', err)

            # Tag node values end up in a shell command run as root, a newline
            # must not be able to start a second command
            out, err = self.ssh_send_cmd(f"{op_runner} show interfaces ethernet $'eth0\\nid'",
                                         op_user, op_password)
            self.assertFalse(out)
            self.assertIn('contains special characters', err)
        finally:
            self.cli_delete(login_path + ['user', op_user])
            self.cli_delete(login_path + ['operator-group', op_group])
            if not ssh_pre_test:
                self.cli_delete(ssh_path)
            self.cli_commit()

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
