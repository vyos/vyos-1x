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

from vyos.utils.serial import is_ttyS

def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print('Usage: monitor_serial.py <arg1> [<arg2>]')
        sys.exit(1)

    first_tty = sys.argv[1]
    if not (is_ttyS(first_tty)):
        sys.exit(1)

    if len(sys.argv) == 3:
        second_tty = sys.argv[2]
        if not (is_ttyS(second_tty)):
            sys.exit(1)

        if first_tty == second_tty:
            os.system(f'iol_serialt {first_tty[4:]} -show')
        else:
            os.system(f'iol_serialt {first_tty[4:]} {second_tty[4:]} -show')
    else:
        os.system(f'iol_serialt {first_tty[4:]} -show')

if __name__ == '__main__':
     main()
