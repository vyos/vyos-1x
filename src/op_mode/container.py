#!/usr/bin/env python3
#
# Copyright (C) 2022-2024 VyOS maintainers and contributors
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

from vyos.utils.process import cmd
from vyos.utils.process import rc_cmd
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

def add_image(name: str):
    """ Pull image from container registry. If registry authentication
    is defined within VyOS CLI, credentials are used to login befroe pull """
    from vyos.configquery import ConfigTreeQuery

    conf = ConfigTreeQuery()
    container = conf.get_config_dict(['container', 'registry'])

    do_logout = False
    if 'registry' in container:
        for registry, registry_config in container['registry'].items():
            if 'disable' in registry_config:
                continue
            if 'authentication' in registry_config:
                do_logout = True
                if {'username', 'password'} <= set(registry_config['authentication']):
                    username = registry_config['authentication']['username']
                    password = registry_config['authentication']['password']
                    cmd = f'podman login --username {username} --password {password} {registry}'
                    rc, out = rc_cmd(cmd)
                    if rc != 0: raise vyos.opmode.InternalError(out)

    rc, output = rc_cmd(f'podman image pull {name}')
    if rc != 0:
        raise vyos.opmode.InternalError(output)

    if do_logout:
        rc_cmd('podman logout --all')

def delete_image(name: str):
    from vyos.utils.process import rc_cmd

    if name == 'all':
        # gather list of all images and pass them to the removal list
        name = cmd('sudo podman image ls --quiet')
        # If there are no container images left, we can not delete them all
        if not name: return
        # replace newline with whitespace
        name = name.replace('\n', ' ')
    rc, output = rc_cmd(f'podman image rm {name}')
    if rc != 0:
        raise vyos.opmode.InternalError(output)

def show_container(raw: bool):
    command = 'podman ps --all'
    container_data = _get_raw_data(command)
    if raw:
        return container_data
    else:
        return cmd(command)

def show_image(raw: bool):
    command = 'podman image ls'
    container_data = _get_raw_data('podman image ls')
    if raw:
        return container_data
    else:
        return cmd(command)

def show_network(raw: bool):
    command = 'podman network ls'
    container_data = _get_raw_data(command)
    if raw:
        return container_data
    else:
        return cmd(command)

def restart(name: str):
    from vyos.utils.process import rc_cmd

    rc, output = rc_cmd(f'systemctl restart vyos-container-{name}.service')
    if rc != 0:
        print(output)
        return None
    print(f'Container "{name}" restarted!')
    return output

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
