#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

def get_uptime_seconds():
  from re import search
  from vyos.util import read_file

  data = read_file("/proc/uptime")
  seconds = search("([0-9\.]+)\s", data).group(1)

  return int(float(seconds))

def get_load_averages():
    from re import search
    from vyos.util import cmd

    data = cmd("uptime")
    matches = search(r"load average:\s*(?P<one>[0-9\.]+)\s*,\s*(?P<five>[0-9\.]+)\s*,\s*(?P<fifteen>[0-9\.]+)\s*", data)

    res = {}
    res[1]  = float(matches["one"])
    res[5]  = float(matches["five"])
    res[15] = float(matches["fifteen"])

    return res

if __name__ == '__main__':
    from vyos.util import seconds_to_human

    print("Uptime: {}\n".format(seconds_to_human(get_uptime_seconds())))

    avgs = get_load_averages()

    print("Load averages:")
    print("1  minute:   {:.02f}%".format(avgs[1]*100))
    print("5  minutes:  {:.02f}%".format(avgs[5]*100))
    print("15 minutes:  {:.02f}%".format(avgs[15]*100))
