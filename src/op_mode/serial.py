#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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

import sys, typing

import vyos.opmode
from vyos.utils.serial import restart_login_consoles as _restart_login_consoles

def restart_console(device_name: typing.Optional[str]):
    # Service control moved to vyos.utils.serial to unify checks and prompts. 
    # If users are connected, we want to show an informational message and a prompt
    # to continue, verifying that the user acknowledges possible interruptions. 
    if device_name:
        _restart_login_consoles(prompt_user=True, quiet=False, devices=[device_name])
    else:
        _restart_login_consoles(prompt_user=True, quiet=False)

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
