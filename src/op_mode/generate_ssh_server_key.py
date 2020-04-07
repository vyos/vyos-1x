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

import sys

from vyos.util import ask_yes_no
from vyos.util import cmd

if not ask_yes_no('Do you really want to remove the existing SSH host keys?'):
    sys.exit(0)

cmd('sudo rm -v /etc/ssh/ssh_host_*')
cmd('sudo dpkg-reconfigure openssh-server')
cmd('sudo systemctl restart ssh')
