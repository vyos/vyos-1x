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

from vyos.utils.io import ask_yes_no
from vyos.utils.process import cmd
from vyos.utils.process import DEVNULL

if not ask_yes_no("This will clear all currently tracked and expected connections. Continue?"):
    sys.exit(1)
else:
    cmd('/usr/sbin/conntrack -F', stderr=DEVNULL)
    cmd('/usr/sbin/conntrack -F expect', stderr=DEVNULL)
