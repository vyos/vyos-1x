#!/usr/bin/env python3
#
# Copyright (C) VyOS Inc.
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
import re
import typing
import tabulate

import vyos.opmode
from vyos.utils.activate import get_activation_scripts
from vyos.utils.activate import set_activation as util_activate
from vyos.utils.activate import get_activation
from vyos.utils.activate import ActiveOpt
from vyos.utils.io import ask_yes_no
from vyos.base import Warning as Warn


def _get_raw_data() -> dict:
    return get_activation_scripts()


def _split_name(name: str) -> tuple[str, str]:
    # script names are guaranteed to have this format by construction:
    # cf. scripts/generate-activation-scripts-json.py
    match = re.match(r'(\d+)\-(.+)', name)
    if match is None:
        return '0', '_'
    prio, base_name = match.groups()
    return prio, base_name


def _find_full_name(name: str) -> typing.Optional[str]:
    script_names = list(_get_raw_data())
    result = list(filter(lambda s: s.endswith(name), script_names))

    return result[0] if result else None


def show_list(raw: bool) -> typing.Optional[list]:
    scripts = _get_raw_data()
    data = []
    for key in scripts.keys():
        _, name = _split_name(key)
        data.append(name)

    if raw:
        return data

    print(*data)
    return None


def show_opts(raw: bool) -> typing.Optional[list]:
    opts = list(typing.get_args(ActiveOpt))

    if raw:
        return opts

    print(*opts)
    return None


def _format_scripts(scripts: dict):
    headers = ['name', 'activate on reboot', 'priority']
    data = []
    for key in scripts.keys():
        prio, name = _split_name(key)
        value = scripts[key]
        data.append([name, value, prio])

    print('Activation units:')
    print(tabulate.tabulate(data, headers))


def show(raw: bool):
    activation_dict = _get_raw_data()
    if raw:
        return activation_dict
    return _format_scripts(activation_dict)


def set_active(name: str, value: ActiveOpt, no_prompt: bool = False):
    PROMPT_ENABLED = f'This will set {name} active on subsequent reboots. Proceed ?'
    PROMPT_ONCE = f'This will set {name} active only for the next reboot. Proceed ?'
    PROMPT_OFF = f'This will set {name} inactive. Proceed ?'
    UNCHANGED = f'{name} is already set to {value}'
    UNKNOWN = 'None such'

    full_name = _find_full_name(name)
    if not full_name:
        Warn(f'No activation unit {name}')
        return

    state = get_activation(full_name)

    if state == 'never':
        Warn(f'{name} has been set to \'never\' and should not be reset')
        return

    if value == state:
        print(UNCHANGED)
        return

    if value not in list(typing.get_args(ActiveOpt)):
        Warn(f'No such value {value}')
        return

    match value:
        case 'enabled':
            message = PROMPT_ENABLED
        case 'once':
            message = PROMPT_ONCE
        case 'off':
            message = PROMPT_OFF
        case _:
            # not reached
            message = UNKNOWN

    if no_prompt or ask_yes_no(message, default=True):
        util_activate(full_name, value)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
