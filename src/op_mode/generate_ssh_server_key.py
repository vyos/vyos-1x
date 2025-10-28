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

# PERLE - vyos changed to call service_ssh.py, but we need to still remove the .tpm tss2 files
# cmd('rm -v /etc/ssh/ssh_host_*')
# cmd('dpkg-reconfigure openssh-server')

cmd('sudo rm -v /etc/ssh/ssh_host_* || true')
cmd('sudo rm -v /etc/ssh/ssh_tpm_host_* || true')

# cmd('ssh-tpm-keygen -A')
# cmd('ssh-keygen -q -N "" -t dsa -f /etc/ssh/ssh_host_dsa_key')
# cmd('ssh-keygen -q -N "" -t ed25519 -f /etc/ssh/ssh_host_ed25519_key')

cmd(f'{conf_mode_dir}/service_ssh.py')

# PERLE - restart of the tpm key agent now called from logic in service_ssh.py 
# cmd('systemctl restart ssh-tpm-agent')
# cmd('systemctl restart ssh-tpm-agent.socket')
