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

import errno
import json
import os
import pwd
import stat
import subprocess
import unittest
from time import monotonic, sleep

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.utils.process import is_systemd_service_running
from vyos.utils.process import cmdl
from vyos.defaults import vyos_configd_socket_path

service_name = 'vyos-configd.service'
socket_path = vyos_configd_socket_path.removeprefix('ipc://')

# Use a real AF_UNIX connect in a separate process with the account's actual
# credentials. A ZeroMQ connect can be queued and appear to succeed even when
# the kernel rejects the underlying connection.
socket_probe = '''
import json
import os
import pwd
import socket
import sys

account = pwd.getpwnam(sys.argv[2])
os.initgroups(account.pw_name, account.pw_gid)
os.setgid(account.pw_gid)
os.setuid(account.pw_uid)

with open('/proc/self/status', encoding='utf-8') as status_file:
    cap_eff = next(line.split(':', 1)[1].strip() for line in status_file
                   if line.startswith('CapEff:'))

client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.settimeout(2)
try:
    client.connect(sys.argv[1])
except OSError as error:
    connect_errno = error.errno
else:
    connect_errno = 0
finally:
    client.close()

print(json.dumps({'uid': os.geteuid(), 'gid': os.getegid(),
                  'groups': os.getgroups(), 'cap_eff': cap_eff,
                  'connect_errno': connect_errno}))
'''

class TestConfigdInit(unittest.TestCase):
    def setUp(self):
        self.running_state = is_systemd_service_running(service_name)
        # always forward to base class
        super().setUp()

    def tearDown(self):
        if not self.running_state:
            cmdl(['systemctl', 'stop', service_name], sudo=True)
        # always forward to base class
        super().tearDown()

    def test_configd_init(self):
        if not self.running_state:
            cmdl(['systemctl', 'start', service_name], sudo=True)
            # allow time for init to succeed/fail
            sleep(2)
        self.assertTrue(is_systemd_service_running(service_name))

    def test_configd_socket_permissions(self):
        if not self.running_state:
            cmdl(['systemctl', 'start', service_name], sudo=True)

        deadline = monotonic() + 5
        while not os.path.exists(socket_path) and monotonic() < deadline:
            sleep(0.1)

        socket_stat = os.lstat(socket_path)
        print(
            f'{socket_path}: uid={socket_stat.st_uid} gid={socket_stat.st_gid} '
            f'mode={stat.S_IMODE(socket_stat.st_mode):04o}'
        )
        self.assertTrue(stat.S_ISSOCK(socket_stat.st_mode))
        self.assertEqual(socket_stat.st_uid, 0)
        self.assertEqual(stat.S_IMODE(socket_stat.st_mode), 0o600)

        parent_stat = os.stat(os.path.dirname(socket_path))
        print(
            f'{os.path.dirname(socket_path)}: uid={parent_stat.st_uid} '
            f'gid={parent_stat.st_gid} '
            f'mode={stat.S_IMODE(parent_stat.st_mode):04o}'
        )
        self.assertEqual(parent_stat.st_uid, 0)
        self.assertEqual(stat.S_IMODE(parent_stat.st_mode) & 0o022, 0)

        for account in ('nobody', '_kea', 'root'):
            try:
                expected_uid = pwd.getpwnam(account).pw_uid
            except KeyError:
                if account == '_kea':
                    print('_kea account absent; skipping its socket probe')
                    continue
                raise

            with self.subTest(account=account):
                result = subprocess.run(
                    [
                        'sudo',
                        '-n',
                        '--',
                        '/usr/bin/python3',
                        '-c',
                        socket_probe,
                        socket_path,
                        account,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                probe = json.loads(result.stdout)
                print(
                    f"{account}: uid={probe['uid']} gid={probe['gid']} "
                    f"groups={probe['groups']} CapEff={probe['cap_eff']} "
                    f"connect_errno={probe['connect_errno']}"
                )
                self.assertEqual(probe['uid'], expected_uid, probe)

                if account != 'root':
                    # CAP_DAC_OVERRIDE would bypass inode permissions; a
                    # privileged probe would not represent an ordinary client.
                    self.assertEqual(int(probe['cap_eff'], 16) & 0x2, 0, probe)

                expected_errno = 0 if account == 'root' else errno.EACCES
                self.assertEqual(probe['connect_errno'], expected_errno, probe)

        self.assertTrue(is_systemd_service_running(service_name))

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
