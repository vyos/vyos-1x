#!/usr/bin/env python3
#
# Copyright (C) VyOS Inc.
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

from argparse import ArgumentParser
from shlex import split as shlex_split

from vyos.utils.config import write_saved_value

def _split_quoted(s: str) -> list[str]:
    parts = shlex_split(s)
    if not parts:
        raise ValueError('empty string')
    return parts

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument(
        '--path',
        required=True,
        help='Quoted CLI path, e.g. "system console device ttyS1 speed"',
    )
    parser.add_argument(
        '--value',
        required=False,
        help='Value for the node, e.g. "9600". If omitted, creates a valueless node.',
    )
    parser.add_argument(
        '--config-file',
        required=True,
        help=f'Path to saved config.boot',
    )
    args = parser.parse_args()

    path = _split_quoted(args.path)
    write_saved_value(path, value=args.value, config_path=args.config_file)
