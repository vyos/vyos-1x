#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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

import sys

import vyos.opmode

def _get_raw_data():
    from vyos.utils.system import get_uptime_seconds, get_load_averages
    from vyos.utils.convert import seconds_to_human

    res = {}
    uptime_seconds = get_uptime_seconds()
    res["uptime"] = seconds_to_human(uptime_seconds, separator=' ')
    res["load_average"] = get_load_averages()

    return res

def _get_formatted_output(data):
    out = "Uptime: {}\n\n".format(data["uptime"])
    avgs = data["load_average"]
    out += "Load averages:\n"
    out += "1  minute:   {:.01f}%\n".format(avgs[1]*100)
    out += "5  minutes:  {:.01f}%\n".format(avgs[5]*100)
    out += "15 minutes:  {:.01f}%\n".format(avgs[15]*100)

    return out

def show(raw: bool):
    uptime_data = _get_raw_data()

    if raw:
        return uptime_data
    else:
        return _get_formatted_output(uptime_data)

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
