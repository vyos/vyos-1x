#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

import sys
from argparse import ArgumentParser
from tabulate import tabulate

from vyos.priority import get_priority_data

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--legacy-format', action='store_true',
                        help="format output for comparison with legacy 'priority.pl'")
    args = parser.parse_args()

    prio_list = get_priority_data()
    if args.legacy_format:
        for p in prio_list:
            print(f'{p[2]} {"/".join(p[0])}')
        sys.exit(0)

    l = []
    for p in prio_list:
        l.append((p[2], p[1], p[0]))
    headers = ['priority', 'owner', 'path']
    out = tabulate(l, headers, numalign='right')
    print(out)
