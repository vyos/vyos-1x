#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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

import json
import sys

from sys import exit

from vyos.util import cmd

import vyos.opmode


def _get_json_data(command: str) -> list:
    """
    Get container command format JSON
    """
    return cmd(f'{command} --format json')


def _get_raw_data(command: str) -> list:
    json_data = _get_json_data(command)
    data = json.loads(json_data)
    return data


def show_container(raw: bool):
    command = 'sudo podman ps --all'
    container_data = _get_raw_data(command)
    if raw:
        return container_data
    else:
        return cmd(command)


def show_image(raw: bool):
    command = 'sudo podman image ls'
    container_data = _get_raw_data('sudo podman image ls')
    if raw:
        return container_data
    else:
        return cmd(command)


def show_network(raw: bool):
    command = 'sudo podman network ls'
    container_data = _get_raw_data(command)
    if raw:
        return container_data
    else:
        return cmd(command)


def restart(name: str):
    from vyos.util import rc_cmd

    rc, output = rc_cmd(f'sudo podman restart {name}')
    if rc != 0:
        print(output)
        return None
    print(f'Container name "{name}" restarted!')
    return output


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
