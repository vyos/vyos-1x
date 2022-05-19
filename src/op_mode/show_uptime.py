#!/usr/bin/env python3
#
# Copyright (C) 2021-2022 VyOS maintainers and contributors
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
    from vyos.cpu import get_core_count

    data = cmd("uptime")
    matches = search(r"load average:\s*(?P<one>[0-9\.]+)\s*,\s*(?P<five>[0-9\.]+)\s*,\s*(?P<fifteen>[0-9\.]+)\s*", data)

    core_count = get_core_count()

    res = {}
    res[1]  = float(matches["one"]) / core_count
    res[5]  = float(matches["five"]) / core_count
    res[15] = float(matches["fifteen"]) / core_count

    return res

def get_raw_data():
    from vyos.util import seconds_to_human

    res = {}
    res["uptime_seconds"] = get_uptime_seconds()
    res["uptime"] = seconds_to_human(get_uptime_seconds())
    res["load_average"] = get_load_averages()

    return res

def get_formatted_output():
    data = get_raw_data()

    out = "Uptime: {}\n\n".format(data["uptime"])
    avgs = data["load_average"]
    out += "Load averages:\n"
    out += "1  minute:   {:.01f}%\n".format(avgs[1]*100)
    out += "5  minutes:  {:.01f}%\n".format(avgs[5]*100)
    out += "15 minutes:  {:.01f}%\n".format(avgs[15]*100)

    return out

if __name__ == '__main__':
    print(get_formatted_output())
