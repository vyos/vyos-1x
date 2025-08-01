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

import re
import argparse
from vyos.utils.serial import find_all_ttyS_devices

def trim_list_from_match(full_tty_list, start_tty):
    try:
        index = next(i for i, item in enumerate(full_tty_list) if start_tty in item)
        return full_tty_list[index:]
    except StopIteration:
        return full_tty_list

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-g", "--greater", type=str, help="List serial with tty number greater than input")
    args = parser.parse_args()
    final_list = []
    # Autocomplete uses runtime state rather than the config tree, as a manual
    # restart/cleanup may be needed for deleted devices.
    tty_list = sorted(find_all_ttyS_devices(), key=lambda x: int(re.search(r'\d+', x).group()))

    if args.greater:
        final_list = trim_list_from_match(tty_list, args.greater)
    else:
        final_list = tty_list
    tty_completions = [ '<text>' ] + final_list
    print(' '.join(tty_completions))
