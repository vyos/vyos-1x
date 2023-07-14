#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
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
from sys import argv, exit
from vyos.utils.process import call
from vyos.utils.commit import commit_in_progress

if __name__ == '__main__':
    if (len(argv) < 1):
        print('Must specify OpenVPN interface name!')
        exit(1)

    interface = argv[1]
    if os.path.isfile(f'/run/openvpn/{interface}.conf'):
        if commit_in_progress():
            print('Cannot restart OpenVPN while a commit is in progress')
            exit(1)
        call(f'systemctl restart openvpn@{interface}.service')
    else:
        print(f'OpenVPN interface "{interface}" does not exist!')
        exit(1)
