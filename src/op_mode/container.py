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

import typing
import json
import shutil
import sys
import subprocess

from pathlib import Path
from vyos.defaults import directories
from vyos.utils.process import cmd
from vyos.utils.process import rc_cmd
from vyos.utils.process import run
import vyos.opmode

def clean_layer(name: str) -> int:
    def layer_id_from_containers(name: str) -> str | None:
        if containers.is_file():
            try:
                index = json.loads(containers.read_text())
            except Exception:
                return None
            for item in index:
                if name in item.get("names", []):
                    return item.get("layer")
        return None

    def purge_layer_by_id(layer_id: str):
        layer_dir = overlay_root / layer_id

        # Remove the overlay ID directory
        shutil.rmtree(layer_dir, ignore_errors=True)
    storage_dir = Path(directories['podman_storage'])
    overlay_root = storage_dir / "overlay"
    containers = storage_dir / "overlay-containers/containers.json"
    unit = f"vyos-container-{name}.service"
    layer_id = layer_id_from_containers(name)
    if not layer_id:
        # No mapping found; nothing to do
        return 2

    purge_layer_by_id(layer_id)

    # Reinitiate the container's overlay layer
    cmd(f"rm -f /run/{unit}.cid /run/{unit}.pid")
    cmd(f"systemctl reset-failed {unit}")
    result = run(f"systemctl start {unit}")
    return result

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
    print(output)
    if rc != 0:
        raise vyos.opmode.InternalError(output)

    if do_logout:
        rc_cmd('podman logout --all')

def delete_image(name: str, force: typing.Optional[bool] = False):
    from vyos.utils.process import rc_cmd

    if name == 'all':
        # gather list of all images and pass them to the removal list
        name = cmd('sudo podman image ls --quiet')
        # If there are no container images left, we can not delete them all
        if not name: return
        # replace newline with whitespace
        name = name.replace('\n', ' ')
        # convert to list
        name = name.split()
    else:
        # convert str -> list for further processing down the line
        name = [name]

    for image in name:
        # convert the truncated image ID to a full image ID
        rc, ancestor = rc_cmd(f'podman inspect {image} --format "{{{{.Id}}}}"', stderr=None)
        if rc != 0:
            raise vyos.opmode.InternalError(ancestor)
        # check if the image ID is an ancestor of any running container
        rc, in_use = rc_cmd(f'podman ps --filter ancestor={ancestor} -q', stderr=None)
        if rc != 0:
            raise vyos.opmode.InternalError(in_use)

        if bool(in_use):
            error = f'Cannot delete image "{image}" because it is currently '\
                    f'being used by container "{in_use}"!'
            raise vyos.opmode.InternalError(error)

        tmp = f'podman image rm {image}'
        if force: tmp += ' --force'

        rc, output = rc_cmd(tmp)
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
    from vyos.config import Config
    from vyos.container import restart_network

    rc, output = rc_cmd(f'systemctl restart vyos-container-{name}.service')
    if rc != 0:
        rc2 = clean_layer(name)
        if rc2 != 0:
            print(output)
            return None
    if rc == 0:
        conf = Config()
        container = conf.get_config_dict(['container'], key_mangling=('-', '_'),
                                    no_tag_node_value_mangle=True,
                                    get_first_key=True,
                                    with_recursive_defaults=True)
        restart_network(container)
    print(f'Container "{name}" restarted!')
    return output

def show_log(name: str, follow: bool = False, raw: bool = False):
    """
    Show or monitor logs for a specific container.
    Use --follow to continuously stream logs.
    """
    from vyos.configquery import ConfigTreeQuery
    conf = ConfigTreeQuery()
    container = conf.get_config_dict(['container', 'name', name],  get_first_key=True, with_recursive_defaults=True)
    log_type = container.get('log-driver')
    if log_type == 'k8s-file':
        if follow:
            log_command_list = ['sudo', 'podman', 'logs', '--follow', '--names', name]
        else:
            log_command_list = ['sudo', 'podman', 'logs', '--names', name]
    elif log_type == 'journald':
        if follow:
            log_command_list = ['journalctl', '--follow', '--unit', f'vyos-container-{name}.service']
        else:
            log_command_list = ['journalctl', '-e', '--no-pager', '--unit', f'vyos-container-{name}.service']
    elif log_type == 'none':
        print(f'Container "{name}" has disabled logs.')
        return None
    else:
        raise vyos.opmode.InternalError(f'Unknown log type "{log_type}" for container "{name}".')

    process = None
    try:
        process = subprocess.Popen(log_command_list,
                                   stdout=sys.stdout,
                                   stderr=sys.stderr)
        process.wait()
    except KeyboardInterrupt:
        if process:
            process.terminate()
            process.wait()
        return None
    except Exception as e:
        raise vyos.opmode.InternalError(f"Error starting logging command: {e} ")
    return None


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
