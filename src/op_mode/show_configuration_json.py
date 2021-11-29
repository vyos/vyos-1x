#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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
import json

from vyos.configquery import ConfigTreeQuery


config = ConfigTreeQuery()
c = config.get_config_dict()

parser = argparse.ArgumentParser()
parser.add_argument("-p", "--pretty", action="store_true", help="Show pretty configuration in JSON format")


if __name__ == '__main__':
    args = parser.parse_args()

    if args.pretty:
        print(json.dumps(c, indent=4))
    else:
        print(json.dumps(c))
