#!/usr/bin/env python3
#
# Copyright (C) 2016-2024 VyOS maintainers and contributors
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
# This script is a helper to run VTYSH commands for "show evpn", allowing for the --raw flag to output JSON

import sys
import typing
import json

import vyos.opmode
from vyos.utils.process import cmd

def show_evpn(raw: bool, command: typing.Optional[str]):
    if raw:
        command = f"{command} json"
        evpnDict = {}
        try:
            evpnDict['evpn'] = json.loads(cmd(f"vtysh -c '{command}'"))
        except:
            raise vyos.opmode.DataUnavailable(f"\"{command.replace(' json', '')}\" is invalid or has no JSON option")

        return evpnDict
    else:
        return cmd(f"vtysh -c '{command}'")

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
