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
import argparse

from vyos.utils.process import cmd


def validate_hex_size(value):
    """Validate that the hex_size is between 32 and 512."""
    try:
        value = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("hex_size must be integer.")

    if value < 32 or value > 512:
        raise argparse.ArgumentTypeError("hex_size must be between 32 and 512.")
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hex_size",
        type=validate_hex_size,
        help='PKS value size in hex format. Default is 32 bytes.',
        default=32,

        required=False,
    )
    args = parser.parse_args()

    print(cmd(f'openssl rand -hex {args.hex_size}'))