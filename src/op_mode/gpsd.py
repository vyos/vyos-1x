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

import sys

import vyos.opmode
from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import cmd

def _is_configured():
    # Check if ntp is configured
    config = ConfigTreeQuery()
    if not config.exists("service gpsd"):
        raise vyos.opmode.UnconfiguredSubsystem("gpsd service is not enabled")

def show_location():
    _is_configured()
    import json

    raw = cmd(
        'gpspipe -w -x 3 | '
        'jq --unbuffered -c \'select(.class=="TPV" and (.lat? and .lon?)) | {lat:.lat, lon:.lon}\' | '
        'head -n 1'
    ).strip()

    if not raw:
        print("No location available")
    else:
        data = json.loads(raw)
        lat = data["lat"]
        lon = data["lon"]
        print(f"Latitude:  {lat}")
        print(f"Longitude: {lon}")


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)