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

import os
import sys
import re

from vyos.util import popen

# chech connection to pptp and l2tp daemon
def get_sessions():
    absent_pptp = False
    absent_l2tp = False
    pptp_cmd = "accel-cmd -p 2003 show sessions"
    l2tp_cmd = "accel-cmd -p 2004 show sessions"
    err_pattern = "^Connection.+failed$"
    # This value for chack only output header without sessions.
    len_def_header = 170
    
    # Check pptp
    output, err = popen(pptp_cmd, decode='utf-8')
    if not err and len(output) > len_def_header and not re.search(err_pattern, output):
        print(output)
    else:
        absent_pptp = True

    # Check l2tp
    output, err = popen(l2tp_cmd, decode='utf-8')
    if not err and len(output) > len_def_header and not re.search(err_pattern, output):
        print(output)
    else:
        absent_l2tp = True

    if absent_l2tp and absent_pptp:
        print("No active remote access VPN sessions")


def main():
    get_sessions()


if __name__ == '__main__':
    main()
