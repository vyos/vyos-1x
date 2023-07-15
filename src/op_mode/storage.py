#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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
#

import sys

import vyos.opmode
from vyos.utils.process import cmd

# FIY: As of coreutils from Debian Buster and Bullseye,
# the outpt looks like this:
#
# $ df -h -t ext4 --output=source,size,used,avail,pcent
# Filesystem      Size  Used Avail Use%
# /dev/sda1        16G  7.6G  7.3G  51%
#
# Those field names are automatically normalized by vyos.opmode.run,
# so we don't touch them here,
# and only normalize values.

def _get_system_storage(only_persistent=False):
    if not only_persistent:
        cmd_str = 'df -h -x squashf'
    else:
        cmd_str = 'df -h -t ext4 --output=source,size,used,avail,pcent'

    res = cmd(cmd_str)

    return res

def _get_raw_data():
    from re import sub as re_sub
    from vyos.utils.convert import human_to_bytes

    out =  _get_system_storage(only_persistent=True)
    lines = out.splitlines()
    lists = [l.split() for l in lines]
    res = {lists[0][i]: lists[1][i] for i in range(len(lists[0]))}

    res["Size"] = human_to_bytes(res["Size"])
    res["Used"] = human_to_bytes(res["Used"])
    res["Avail"] = human_to_bytes(res["Avail"])
    res["Use%"] = re_sub(r'%', '', res["Use%"])

    return res

def _get_formatted_output():
    return _get_system_storage()

def show(raw: bool):
    if raw:
        return _get_raw_data()

    return _get_formatted_output()


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)

