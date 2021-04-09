#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

import os

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configdict import node_changed
from vyos.configdict import leaf_node_changed
from vyos import ConfigError
from vyos.util import cmd, process_named_running
from vyos.template import render
from vyos.xml import defaults
from vyos import airbag
import json
airbag.enable()

config_containers_registry = '/etc/containers/registries.conf'
config_containers_storage = '/etc/containers/storage.conf'

# Container management functions
def container_exists(name):
    '''
       https://docs.podman.io/en/latest/_static/api.html#operation/ContainerExistsLibpod
       Check if container exists. Response codes.
       204 - container exists
       404 - no such container
    '''
    c = cmd(f"curl --unix-socket /run/podman/podman.sock 'http://d/v3.0.0/libpod/containers/{name}/exists'")
    # If container exists it return status code "0"
    # This code not displayed
    if c == "":
        # Container exists
        return True
    else:
        # Container not exists
        return False

def container_status(name):
    '''
       https://docs.podman.io/en/latest/_static/api.html#operation/ContainerInspectLibpod
    '''
    c = cmd(f"curl --unix-socket /run/podman/podman.sock 'http://d/v3.0.0/libpod/containers/{name}/json'")
    data = json.loads(c)
    status = data['State']['Status']

    return status

def container_stop(name):
    c = cmd(f'podman stop {name}')

def container_start(name):
    c = cmd(f'podman start {name}')

def ctnr_network_exists(name):
    # Check explicit name for network.
    c = cmd(f'podman network ls --quiet --filter name=^{name}$')
    # If network name is found, return true
    if bool(c) == True:
        return True
    else:
        return False


# Common functions
def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['container']
    container = conf.get_config_dict(base, get_first_key=True)
    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    container = dict_merge(default_values, container)

    if 'name' in container or 'network' in container:
        container['configured'] = True

    # Delete container network, delete containers
    dict = {}
    tmp_net = node_changed(conf, ['container', 'network'])
    if tmp_net:
        dict = dict_merge({'net_remove' : tmp_net}, dict)
        container.update(dict)

    tmp_name = node_changed(conf, ['container', 'name'])
    if tmp_name:
        dict = dict_merge({'container_remove' : tmp_name}, dict)
        container.update(dict)

    return container

def verify(container):
    # bail out early - looks like removal from running config
    if not container:
        return None

    # Add new container
    if 'name' in container:
        for cont, container_config in container['name'].items():
            # Dont add container with wrong/undefined name network
            if 'network' in container_config and 'network' in container:
                if list(container_config['network'])[0] not in container['network']:
                    # Don't allow delete network if container use this network.
                    raise ConfigError('Netowrk with name: {0} shuld be specified!'.format(list(container_config['network'])[0]))

            # If image not defined
            if 'image' not in container_config:
                raise ConfigError(f'Image for container "{cont}" is required!')

            # If 'allow-host-networks' or 'network' not set.
            if 'allow-host-networks' not in container_config and 'network' not in container_config:
                raise ConfigError(f'"Network" or "allow-host-networks" for container "{cont}" is required!')

            # If set both parameters for networks (host and user-defined). We require only one.
            if 'allow-host-networks' in container_config and 'network' in container_config:
                raise ConfigError(f'"allow-host-networks" and "network" for "{cont}" cannot be both configured at the same time!')

    # Add new network
    if 'network' in container:
        for net in container['network']:
            # If ipv4-prefix not defined for user-defined network
            if 'ipv4-prefix' not in container['network'][net]:
                raise ConfigError(f'IPv4 prefix for network "{net}" is required!')

    # Don't allow to remove network which used for container
    if 'net_remove' in container:
        for net in container['net_remove']:
            if 'name' in container:
                for cont in container['name']:
                    if 'network' in container['name'][cont]:
                        if net in container['name'][cont]['network']:
                            raise ConfigError(f'Can\'t remove network "{net}" used for "{cont}"')

    return None

def generate(container):
    # bail out early - looks like removal from running config
    if not container:
        return None

    render(config_containers_registry, 'containers/registry.tmpl', container)
    render(config_containers_storage, 'containers/storage.tmpl', container)

    return None

def apply(container):
    # Delete old containers if needed. We can't delete running container
    # Option "--force" allows to delete containers with any status
    if 'container_remove' in container:
        for name in container['container_remove']:
            if container_status(name) == 'running':
                cmd(f'podman stop {name}')
            cmd(f'podman rm --force {name}')
            print(f'Container "{name}" deleted')

    # Delete old networks if needed
    if 'net_remove' in container:
        for net in container['net_remove']:
            cmd(f'podman network rm {net}')

    # Add network
    if 'network' in container:
        for net in container['network']:
            # Check if the network has already been created
            if ctnr_network_exists(net) is False:
                prefix = container['network'][net]['ipv4-prefix']
                if container['network'][net]['ipv4-prefix']:
                    # Create user-defined network
                    try:
                        cmd(f'podman network create {net} --subnet={prefix}')
                    except:
                        print(f'Can\'t add network {net}')

    # Add container
    if 'name' in container:
        for name in container['name']:
            # Check if the container has already been created
            #if len(cmd(f'podman ps -a --filter "name=^{name}$" -q')) == 0:
            if container_exists(name) is False:
                image = container['name'][name]['image']

                # Check/set environment options "-e foo=bar"
                env_opt = ''
                if 'environment' in container['name'][name]:
                    env_opt = '-e '
                    env_opt += " -e ".join(f"{k}={v['value']}" for k, v in container['name'][name]['environment'].items())

                if 'allow-host-networks' in container['name'][name]:
                    try:
                        cmd(f'podman run -dit --name {name} --net host {env_opt} {image}')
                    except:
                        print(f'Can\'t add container {name}')

                else:
                    for net in container['name'][name]['network']:
                        if container['name'][name]['image']:
                            ipparam = ''
                            if 'address' in container['name'][name]['network'][net]:
                                ipparam = '--ip {}'.format(container['name'][name]['network'][net]['address'])
                            try:
                                cmd(f'podman run --name {name} -dit --net {net} {ipparam} {env_opt} {image}')
                            except:
                                print(f'Can\'t add container {name}')
            # Else container is already created. Just start it.
            # It's needed after reboot.
            else:
                if container_status(name) != 'running':
                    container_start(name)
    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
