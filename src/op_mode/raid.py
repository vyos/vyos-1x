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
import sys

import vyos.opmode
from vyos.raid import add_raid_member
from vyos.raid import delete_raid_member

def add(raid_set_name: str, member: str, by_id: bool = False):
    try:
        add_raid_member(raid_set_name, member, by_id)
    except ValueError as e:
        raise vyos.opmode.IncorrectValue(str(e))

def delete(raid_set_name: str, member: str, by_id: bool = False):
    try:
        delete_raid_member(raid_set_name, member, by_id)
    except ValueError as e:
        raise vyos.opmode.IncorrectValue(str(e))

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)

