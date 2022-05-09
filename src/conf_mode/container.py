#!/usr/bin/env python3
#
# Copyright (C) 2021-2022 VyOS maintainers and contributors
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

from ipaddress import ip_address
from ipaddress import ip_network
from time import sleep
from json import dumps as json_write

from vyos.base import Warning
from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configdict import node_changed
from vyos.util import call
from vyos.util import cmd
from vyos.util import run
from vyos.util import write_file
from vyos.template import inc_ip
from vyos.template import is_ipv4
from vyos.template import is_ipv6
from vyos.template import render
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_containers_registry = '/etc/containers/registries.conf'
config_containers_storage = '/etc/containers/storage.conf'

def _run_rerun(container_cmd):
    counter = 0
    while True:
        if counter >= 10:
            break
        try:
            _cmd(container_cmd)
            break
        except:
            counter = counter +1
            sleep(0.5)

    return None

def _cmd(command):
    if os.path.exists('/tmp/vyos.container.debug'):
        print(command)
    return cmd(command)

def network_exists(name):
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
    tmp = node_changed(conf, base + ['container', 'network'])
    if tmp: container.update({'network_remove' : tmp})

    tmp = node_changed(conf, base + ['container', 'name'])
    if tmp: container.update({'container_remove' : tmp})

    return container

def verify(container):
    # bail out early - looks like removal from running config
    if not container:
        return None

    # Add new container
    if 'name' in container:
        for name, container_config in container['name'].items():
            # Container image is a mandatory option
            if 'image' not in container_config:
                raise ConfigError(f'Container image for "{name}" is mandatory!')

            # Check if requested container image exists locally. If it does not
            # exist locally - inform the user. This is required as there is a
            # shared container image storage accross all VyOS images. A user can
            # delete a container image from the system, boot into another version
            # of VyOS and then it would fail to boot. This is to prevent any
            # configuration error when container images are deleted from the
            # global storage. A per image local storage would be a super waste
            # of diskspace as there will be a full copy (up tu several GB/image)
            # on upgrade. This is the "cheapest" and fastest solution in terms
            # of image upgrade and deletion.
            image = container_config['image']
            if run(f'podman image exists {image}') != 0:
                Warning(f'Image "{image}" used in contianer "{name}" does not exist '\
                        f'locally. Please use "add container image {image}" to add it '\
                        f'to the system! Container "{name}" will not be started!')

            if 'network' in container_config:
                if len(container_config['network']) > 1:
                    raise ConfigError(f'Only one network can be specified for container "{name}"!')

                # Check if the specified container network exists
                network_name = list(container_config['network'])[0]
                if network_name not in container['network']:
                    raise ConfigError(f'Container network "{network_name}" does not exist!')

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

            if 'device' in container_config:
                for dev, dev_config in container_config['device'].items():
                    if 'source' not in dev_config:
                        raise ConfigError(f'Device "{dev}" has no source path configured!')

                    if 'destination' not in dev_config:
                        raise ConfigError(f'Device "{dev}" has no destination path configured!')

                    source = dev_config['source']
                    if not os.path.exists(source):
                        raise ConfigError(f'Device "{dev}" source path "{source}" does not exist!')

            if 'environment' in container_config:
                for var, cfg in container_config['environment'].items():
                    if 'value' not in cfg:
                        raise ConfigError(f'Environment variable {var} has no value assigned!')

            if 'volume' in container_config:
                for volume, volume_config in container_config['volume'].items():
                    if 'source' not in volume_config:
                        raise ConfigError(f'Volume "{volume}" has no source path configured!')

                    if 'destination' not in volume_config:
                        raise ConfigError(f'Volume "{volume}" has no destination path configured!')

                    source = volume_config['source']
                    if not os.path.exists(source):
                        raise ConfigError(f'Volume "{volume}" source path "{source}" does not exist!')

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
                raise ConfigError(f'prefix for network "{network}" must be defined!')

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
        if os.path.exists(config_containers_registry):
            os.unlink(config_containers_registry)
        if os.path.exists(config_containers_storage):
            os.unlink(config_containers_storage)
        return None

    if 'network' in container:
        for network, network_config in container['network'].items():
            tmp = {
                'cniVersion' : '0.4.0',
                'name' : network,
                'plugins' : [{
                    'type': 'bridge',
                    'bridge': f'cni-{network}',
                    'isGateway': True,
                    'ipMasq': False,
                    'hairpinMode': False,
                    'ipam' : {
                        'type': 'host-local',
                        'routes': [],
                        'ranges' : [],
                    },
                }]
            }

            for prefix in network_config['prefix']:
                net = [{'gateway' : inc_ip(prefix, 1), 'subnet' : prefix}]
                tmp['plugins'][0]['ipam']['ranges'].append(net)

                # install per address-family default orutes
                default_route = '0.0.0.0/0'
                if is_ipv6(prefix):
                    default_route = '::/0'
                tmp['plugins'][0]['ipam']['routes'].append({'dst': default_route})

            write_file(f'/etc/cni/net.d/{network}.conflist', json_write(tmp, indent=2))

    render(config_containers_registry, 'container/registries.conf.j2', container)
    render(config_containers_storage, 'container/storage.conf.j2', container)

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
            tmp = f'/etc/cni/net.d/{network}.conflist'
            if os.path.exists(tmp):
                os.unlink(tmp)

    # Add container
    if 'name' in container:
        for name, container_config in container['name'].items():
            image = container_config['image']

            if run(f'podman image exists {image}') != 0:
                # container image does not exist locally - user already got
                # informed by a WARNING in verfiy() - bail out early
                continue

            if 'disable' in container_config:
                # check if there is a container by that name running
                tmp = _cmd('podman ps -a --format "{{.Names}}"')
                if name in tmp:
                    _cmd(f'podman stop {name}')
                    _cmd(f'podman rm --force {name}')
                continue

            memory = container_config['memory']
            restart = container_config['restart']

            # Add capability options. Should be in uppercase
            cap_add = ''
            if 'cap_add' in container_config:
                for c in container_config['cap_add']:
                    c = c.upper()
                    c = c.replace('-', '_')
                    cap_add += f' --cap-add={c}'

            # Add a host device to the container /dev/x:/dev/x
            device = ''
            if 'device' in container_config:
                for dev, dev_config in container_config['device'].items():
                    source_dev = dev_config['source']
                    dest_dev = dev_config['destination']
                    device += f' --device={source_dev}:{dest_dev}'

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

            container_base_cmd = f'podman run --detach --interactive --tty --replace {cap_add} ' \
                                 f'--memory {memory}m --memory-swap 0 --restart {restart} ' \
                                 f'--name {name} {device} {port} {volume} {env_opt}'
            if 'allow_host_networks' in container_config:
                _run_rerun(f'{container_base_cmd} --net host {image}')
            else:
                for network in container_config['network']:
                    ipparam = ''
                    if 'address' in container_config['network'][network]:
                        address = container_config['network'][network]['address']
                        ipparam = f'--ip {address}'

                    _run_rerun(f'{container_base_cmd} --net {network} {ipparam} {image}')

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
