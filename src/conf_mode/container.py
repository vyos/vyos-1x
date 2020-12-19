#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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
from vyos.util import call, cmd, process_named_running
from vyos.template import render
from vyos import airbag
airbag.enable()


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['container']
    container = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

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
    else:
        # Start docker
        docker_pid = process_named_running('dockerd')
        if not docker_pid:
            call('systemctl restart docker.service')

    # Add new container
    if 'name' in container:
        for cont, container_config in container['name'].items():
            # Dont add container with wrong/undefined name network
            if 'network' in container_config and 'network' in container:
                if list(container_config['network'])[0] not in container['network']:
                    # Need to refrase. Don't allow add container with wrong network name.
                    # Don't allow delete network if container use that network.
                    raise ConfigError('Netowrk with name: {0} shuld be specified!'.format(list(container_config['network'])[0]))

            # If image not defined
            if 'image' not in container_config:
                raise ConfigError(f'Image for container "{cont}" is required!')

            # Image should be downloaded before we run the container. Or not?.
            # For example 'docker image ls --format {{.Repository}} --filter "reference=alpine"'
            if 'image' in container_config:
                image = container_config['image']
                repo = cmd(f'docker image ls --format ' + '{{.Repository}}' + f' --filter \"reference={image}\"')
                # Check if image was pulled and present in local images
                if image != repo:
                    raise ConfigError(f'Pull image for container "{name}" is required!\nUse: run add container image {image}')

            # If 'allow-host-networks' or 'network' not set.
            if 'allow_host_networks' not in container_config and 'network' not in container_config:
                raise ConfigError(f'"Network" or "allow-host-networks" for container "{cont}" is required!')

            # If set both parameters for networks (host and user-defined). We require only one.
            if 'allow_host_networks' in container_config and 'network' in container_config:
                raise ConfigError(f'"allow-host-networks" and "network" for "{cont}" cannot be both configured at the same time!')

    # Add new network
    if 'network' in container:
        for net in container['network']:
            # If ipv4-prefix not defined for user-defined network
            if 'ipv4_prefix' not in container['network'][net]:
                raise ConfigError(f'IPv4 prefix for network "{net}" is required!')

    return None

def generate(container):
    # bail out early - looks like removal from running config
    if not container:
        return None

    return None

def apply(container):
    # Delete old networks if needed
    if 'net_remove' in container:
        for net in container['net_remove']:
            call(f'docker network rm {net}')

    # Delete old containers if needed. We can't delete running container
    if 'container_remove' in container:
        for name in container['container_remove']:
            call(f'docker stop {name}')
            call(f'docker rm {name}')

    if not 'configured' in container:
        # Stop docker.service, we should stop docker.socket, otherwise the service won't stop
        call('systemctl stop docker.socket')
        return

    # Add network
    if 'network' in container:
        for net in container['network']:
            # Check if the network has already been created
            if len(cmd(f'docker network ls  --filter "name=^{net}$" -q')) == 0:
                prefix = container['network'][net]['ipv4_prefix']
                if container['network'][net]['ipv4_prefix']:
                    # Create user-defined bridge network
                    try:
                        call(f'docker network create {net} --subnet={prefix}')
                    except:
                        print(f'Can\'t add network {net}')

    # Add container
    if 'name' in container:
        for name in container['name']:
            # Check if the container has already been created
            if len(cmd(f'docker ps -a --filter "name=^{name}$" -q')) == 0:
                image = container['name'][name]['image']

                if 'allow_host_networks' in container['name'][name]:
                    try:
                        call(f'docker run --name {name} -dit --net host --restart unless-stopped {image}')
                    except:
                        print(f'Can\'t add container {name}')

                else:
                    for net in container['name'][name]['network']:
                        if container['name'][name]['image']:
                            ipparam = ''
                            if 'address' in container['name'][name]['network'][net]:
                                ipparam = '--ip {}'.format(container['name'][name]['network'][net]['address'])
                            try:
                                call(f'docker run --name {name} -dit --net {net} {ipparam} --restart unless-stopped {image}')
                            except:
                                print(f'Can\'t add container {name}')

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
