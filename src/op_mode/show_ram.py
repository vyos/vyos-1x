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
#

def get_system_memory():
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

def get_system_memory_human():
    from vyos.util import bytes_to_human

    mem = get_system_memory()

    for key in mem:
        # The Linux kernel exposes memory values in kilobytes,
        # so we need to normalize them
        mem[key] = bytes_to_human(mem[key], initial_exponent=10)

    return mem

if __name__ == '__main__':
    mem = get_system_memory_human()

    print("Total: {}".format(mem["total"]))
    print("Free:  {}".format(mem["free"]))
    print("Used:  {}".format(mem["used"]))

