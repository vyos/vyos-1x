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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys

def get_login_shell_pid():
    pid = os.getpid()

    while pid > 1:
        with open(f'/proc/{pid}/stat') as f:
            fields = f.read().split()
            comm = fields[1].strip('()')
            ppid = int(fields[3])

        if comm == 'vbash':
            try:
                for fd in ('0', '1', '2'):
                    path = os.readlink(f'/proc/{pid}/fd/{fd}')
                    if path.startswith('/dev/pts/'):
                        return pid
            except Exception:
                pass

        pid = ppid

    raise RuntimeError('Login shell not found')

def main():
    ttyname = sys.argv[1]
    user = ''
    shell_pid = -1

    try:
        user = os.getlogin()
    except OSError:
        user = None

    try:
        shell_pid = get_login_shell_pid()
    except RuntimeError as e:
        print(f'Error: {e}')

    if user and shell_pid != -1:
        os.system(f'sudo -u {user} /usr/bin/iol_cm -t {ttyname} -p {shell_pid} 30')
    else:
        print(f'Failed to get current user!')
        exit(1)

if __name__ == '__main__':
     main()
