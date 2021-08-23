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
import json

from ipaddress import ip_address
from ipaddress import ip_network

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configdict import node_changed
from vyos.util import call
from vyos.util import cmd
from vyos.util import run
from vyos.template import render
from vyos.template import is_ipv4
from vyos.template import is_ipv6
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_containers_registry = '/etc/containers/registries.conf'
config_containers_storage = '/etc/containers/storage.conf'

def _cmd(command):
    if os.path.exists('/tmp/vyos.container.debug'):
        print(command)
    return cmd(command)

def ctnr_network_exists(name):
    # Check explicit name for network, returns True if network exists
    c = _cmd(f'podman network ls --quiet --filter name=^{name}$')
    return bool(c)

# Common functions
def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['container']
    container = conf.get_config_dict(base, key_mangling=('-', '_'),
                                     get_first_key=True, no_tag_node_value_mangle=True)
    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    # container base default values can not be merged here - remove and add them later
    if 'name' in default_values:
        del default_values['name']
    container = dict_merge(default_values, container)

    # Merge per-container default values
    if 'name' in container:
        default_values = defaults(base + ['name'])
        for name in container['name']:
            container['name'][name] = dict_merge(default_values, container['name'][name])

    # Delete container network, delete containers
    tmp = node_changed(conf, ['container', 'network'])
    if tmp: container.update({'network_remove' : tmp})

    tmp = node_changed(conf, ['container', 'name'])
    if tmp: container.update({'container_remove' : tmp})

    return container

def verify(container):
    # bail out early - looks like removal from running config
    if not container:
        return None

    # Add new container
    if 'name' in container:
        for name, container_config in container['name'].items():
            if 'network' in container_config:
                if len(container_config['network']) > 1:
                    raise ConfigError(f'Only one network can be specified for container "{name}"!')

                # Check if the specified container network exists
                network_name = list(container_config['network'])[0]
                if network_name not in container['network']:
                    raise ConfigError('Container network "{network_name}" does not exist!')

                if 'address' in container_config['network'][network_name]:
                    if 'network' not in container_config:
                        raise ConfigError(f'Can not use "address" without "network" for container "{name}"!')

                    address = container_config['network'][network_name]['address']
                    network = None
                    if is_ipv4(address):
                        network = [x for x in container['network'][network_name]['prefix'] if is_ipv4(x)][0]
                    elif is_ipv6(address):
                        network = [x for x in container['network'][network_name]['prefix'] if is_ipv6(x)][0]

                    # Specified container IP address must belong to network prefix
                    if ip_address(address) not in ip_network(network):
                        raise ConfigError(f'Used container address "{address}" not in network "{network}"!')

                    # We can not use the first IP address of a network prefix as this is used by podman
                    if ip_address(address) == ip_network(network)[1]:
                        raise ConfigError(f'IP address "{address}" can not be used for a container, '\
                                          'reserved for the container engine!')

            if 'environment' in container_config:
                for var, cfg in container_config['environment'].items():
                    if 'value' not in cfg:
                        raise ConfigError(f'Environment variable {var} has no value assigned!')

            # Container image is a mandatory option
            if 'image' not in container_config:
                raise ConfigError(f'Container image for "{name}" is mandatory!')

            # If 'allow-host-networks' or 'network' not set.
            if 'allow_host_networks' not in container_config and 'network' not in container_config:
                raise ConfigError(f'Must either set "network" or "allow-host-networks" for container "{name}"!')

            # Can not set both allow-host-networks and network at the same time
            if {'allow_host_networks', 'network'} <= set(container_config):
                raise ConfigError(f'"allow-host-networks" and "network" for "{name}" cannot be both configured at the same time!')

    # Add new network
    if 'network' in container:
        for network, network_config in container['network'].items():
            v4_prefix = 0
            v6_prefix = 0
            # If ipv4-prefix not defined for user-defined network
            if 'prefix' not in network_config:
                raise ConfigError(f'prefix for network "{net}" must be defined!')

            for prefix in network_config['prefix']:
                if is_ipv4(prefix): v4_prefix += 1
                elif is_ipv6(prefix): v6_prefix += 1

            if v4_prefix > 1:
                raise ConfigError(f'Only one IPv4 prefix can be defined for network "{network}"!')
            if v6_prefix > 1:
                raise ConfigError(f'Only one IPv6 prefix can be defined for network "{network}"!')


    # A network attached to a container can not be deleted
    if {'network_remove', 'name'} <= set(container):
        for network in container['network_remove']:
            for container, container_config in container['name'].items():
                if 'network' in container_config and network in container_config['network']:
                    raise ConfigError(f'Can not remove network "{network}", used by container "{container}"!')

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
            call(f'podman stop {name}')
            call(f'podman rm --force {name}')

    # Delete old networks if needed
    if 'network_remove' in container:
        for network in container['network_remove']:
            call(f'podman network rm --force {network}')

    # Add network
    if 'network' in container:
        for network, network_config in container['network'].items():
            # Check if the network has already been created
            if not ctnr_network_exists(network) and 'prefix' in network_config:
                tmp = f'podman network create {network}'
                # we can not use list comprehension here as the --ipv6 option
                # must immediately follow the specified subnet!!!
                for prefix in sorted(network_config['prefix']):
                    tmp += f' --subnet={prefix}'
                    if is_ipv6(prefix):
                      tmp += ' --ipv6'
                _cmd(tmp)

    # Add container
    if 'name' in container:
        for name, container_config in container['name'].items():
            # Check if the container has already been created
            image = container_config['image']
            memory = container_config['memory']
            restart = container_config['restart']

            # Check if requested container image exists locally. If it does not, we
            # pull it. print() is the best way to have a good response from the
            # polling process to the user to display progress. If the image exists
            # locally, a user can update it running `update container image <name>`
            tmp = run(f'podman image exists {image}')
            if tmp != 0: print(os.system(f'podman pull {image}'))

            # Check/set environment options "-e foo=bar"
            env_opt = ''
            if 'environment' in container_config:
                for k, v in container_config['environment'].items():
                    env_opt += f" -e \"{k}={v['value']}\""

            # Publish ports
            port = ''
            if 'port' in container_config:
                protocol = ''
                for portmap in container_config['port']:
                    if 'protocol' in container_config['port'][portmap]:
                        protocol = container_config['port'][portmap]['protocol']
                        protocol = f'/{protocol}'
                    else:
                        protocol = '/tcp'
                    sport = container_config['port'][portmap]['source']
                    dport = container_config['port'][portmap]['destination']
                    port += f' -p {sport}:{dport}{protocol}'

            # Bind volume
            volume = ''
            if 'volume' in container_config:
                for vol, vol_config in container_config['volume'].items():
                    svol = vol_config['source']
                    dvol = vol_config['destination']
                    volume += f' -v {svol}:{dvol}'

            container_base_cmd = f'podman run --detach --interactive --tty --replace ' \
                                 f'--memory {memory}m --memory-swap 0 --restart {restart} ' \
                                 f'--name {name} {port} {volume} {env_opt}'
            if 'allow_host_networks' in container_config:
                _cmd(f'{container_base_cmd} --net host {image}')
            else:
                for network in container_config['network']:
                    ipparam = ''
                    if 'address' in container_config['network'][network]:
                        ipparam = '--ip ' + container_config['network'][network]['address']
                    _cmd(f'{container_base_cmd} --net {network} {ipparam} {image}')

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
