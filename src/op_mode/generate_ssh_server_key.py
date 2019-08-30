#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
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

import subprocess
import sys

from vyos.util import ask_yes_no

if not ask_yes_no('Do you really want to remove the existing SSH host keys?'):
    sys.exit(0)
else:
    subprocess.check_call(['sudo rm -v /etc/ssh/ssh_host_*'], shell=True)
    subprocess.check_call(['sudo dpkg-reconfigure openssh-server'], shell=True)
    subprocess.check_call(['sudo systemctl restart ssh'], shell=True)
