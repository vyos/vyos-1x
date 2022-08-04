#!/usr/bin/env python3
#
# Copyright (C) 2021-2022 VyOS maintainers and contributors
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


def _get_system_memory():
    from re import search as re_search

    def find_value(keyword, mem_data):
        regex = keyword + ':\s+(\d+)'
        res = re_search(regex, mem_data).group(1)
        return int(res)

    with open("/proc/meminfo", "r") as f:
        mem_data = f.read()

    total     = find_value('MemTotal', mem_data)
    available = find_value('MemAvailable', mem_data)
    buffers   = find_value('Buffers', mem_data)
    cached    = find_value('Cached', mem_data)

    used = total - available

    res = {
      "total":   total,
      "free":    available,
      "used":    used,
      "buffers": buffers,
      "cached":  cached
    }

    return res

def _get_system_memory_human():
    from vyos.util import bytes_to_human

    mem = _get_system_memory()

    for key in mem:
        # The Linux kernel exposes memory values in kilobytes,
        # so we need to normalize them
        mem[key] = bytes_to_human(mem[key], initial_exponent=10)

    return mem

def _get_raw_data():
    return _get_system_memory_human()

def _get_formatted_output(mem):
    out = "Total: {}\n".format(mem["total"])
    out += "Free:  {}\n".format(mem["free"])
    out += "Used:  {}".format(mem["used"])

    return out

def show(raw: bool):
    ram_data = _get_raw_data()

    if raw:
        return ram_data
    else:
        return _get_formatted_output(ram_data)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)

