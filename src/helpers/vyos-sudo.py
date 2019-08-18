#!/usr/bin/env python3

# Copyright 2019 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import getpass
import grp
import os
import sys


def is_admin() -> bool:
    """Look if current user is in sudo group"""
    current_user = getpass.getuser()
    (_, _, _, admin_group_members) = grp.getgrnam('sudo')
    return current_user in admin_group_members


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Missing command argument')
        sys.exit(1)

    if not is_admin():
        print('This account is not authorized to run this command')
        sys.exit(1)

    os.execvp('sudo', ['sudo'] + sys.argv[1:])
