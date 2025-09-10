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

from sys import exit

from vyos.defaults import directories
from vyos.utils.io import ask_yes_no
from vyos.utils.process import cmd
from vyos.utils.commit import commit_in_progress

if not ask_yes_no('Do you really want to remove the existing SSH host keys?'):
    exit(0)

if commit_in_progress():
    print('Cannot restart SSH while a commit is in progress')
    exit(1)

conf_mode_dir = directories['conf_mode']

cmd('rm -v /etc/ssh/ssh_host_*')
cmd('dpkg-reconfigure openssh-server')
cmd(f'{conf_mode_dir}/service_ssh.py')
