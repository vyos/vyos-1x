#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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

from argparse import ArgumentParser
from vyos.utils.config import read_saved_value

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--path', nargs='*')
    args = parser.parse_args()

    out = read_saved_value(args.path) if args.path else ''
    if isinstance(out, list):
        out = ' '.join(out)
    print(out)
