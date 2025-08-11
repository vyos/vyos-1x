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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import re
import sys, typing

import vyos.opmode
from vyos.utils.serial import restart_login_consoles as _restart_login_consoles
from vyos.utils.serial import send_command_to_iolan
from vyos.utils.serial import find_active_ttyS_devices


def restart_console(device_name: typing.Optional[str]):
    # Service control moved to vyos.utils.serial to unify checks and prompts.
    # If users are connected, we want to show an informational message and a prompt
    # to continue, verifying that the user acknowledges possible interruptions.
    if device_name:
        _restart_login_consoles(prompt_user=True, quiet=False, devices=[device_name])
    else:
        _restart_login_consoles(prompt_user=True, quiet=False)

def restart_serial_tty(device_name_start: typing.Optional[str], device_name_end: typing.Optional[str]):
    active_ttys = find_active_ttyS_devices()

    if device_name_end:
        ttynum_end = int(re.findall(r'\d+', device_name_end)[0])
        ttynum_start = int(re.findall(r'\d+', device_name_start)[0])
        if ttynum_end < ttynum_start:
            raise vyos.opmode.Error('Error: The latter tty number must be greater than the former!')
        for i in range(ttynum_start, ttynum_end + 1):
            if f'ttyS{i}' in active_ttys:
                send_command_to_iolan('relaunch', f'ttyS{i}', '', i, 0, '', 0, 0)
            _restart_login_consoles(prompt_user=True, quiet=False, devices=[f'ttyS{i}'])
    else:
        if device_name_start:
            if device_name_start in active_ttys:
                send_command_to_iolan('relaunch', device_name_start, '', re.findall(r'\d+', device_name_start)[0], 0, '', 0, 0)
            _restart_login_consoles(prompt_user=True, quiet=False, devices=[device_name_start])
        else:
            for device in active_ttys:
                send_command_to_iolan('relaunch', device, '', re.findall(r'\d+', device)[0], 0, '', 0, 0)
            _restart_login_consoles(prompt_user=True, quiet=False)

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
