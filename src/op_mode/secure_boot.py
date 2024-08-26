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

import sys
import vyos.opmode

from vyos.utils.boot import is_uefi_system
from vyos.utils.system import get_secure_boot_state

def _get_raw_data(name=None):
    sb_data = {
        'state' : get_secure_boot_state(),
        'uefi' : is_uefi_system()
    }
    return sb_data

def _get_formatted_output(raw_data):
    if not raw_data['uefi']:
        print('System run in legacy BIOS mode!')
    state = 'enabled' if raw_data['state'] else 'disabled'
    return f'SecureBoot {state}'

def show(raw: bool):
    sb_data = _get_raw_data()
    if raw:
        return sb_data
    else:
        return _get_formatted_output(sb_data)

if __name__ == "__main__":
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
