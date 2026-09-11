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
#

import sys

import vyos.opmode
from vyos.utils.memory import get_memory_info


def _get_raw_data():
    mem_info = get_memory_info()

    total = mem_info['MemTotal']
    available = mem_info['MemAvailable']
    buffers = mem_info['Buffers']
    cached = mem_info['Cached']

    used = total - available

    mem_data = {
      "total":   total,
      "free":    available,
      "used":    used,
      "buffers": buffers,
      "cached":  cached
    }

    for key in mem_data:
        # The Linux kernel exposes memory values in kilobytes,
        # so we need to normalize them
        mem_data[key] = mem_data[key] * 1024

    return mem_data

def _get_formatted_output(mem):
    from vyos.utils.convert import bytes_to_human

    # For human-readable outputs, we convert bytes to more convenient units
    # (100M, 1.3G...)
    for key in mem:
        mem[key] = bytes_to_human(mem[key])

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

