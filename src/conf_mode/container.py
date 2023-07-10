#!/usr/bin/env python3
#
# Copyright (C) 2021-2023 VyOS maintainers and contributors
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

from hashlib import sha256
from ipaddress import ip_address
from ipaddress import ip_network
from json import dumps as json_write

from vyos.base import Warning
from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configdict import node_changed
from vyos.configdict import is_node_changed
from vyos.configverify import verify_vrf
from vyos.ifconfig import Interface
from vyos.util import call
from vyos.util import cmd
from vyos.util import run
from vyos.util import rc_cmd
from vyos.util import write_file
from vyos.template import inc_ip
from vyos.template import is_ipv4
from vyos.template import is_ipv6
from vyos.template import render
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_containers = '/etc/containers/containers.conf'
config_registry = '/etc/containers/registries.conf'
config_storage = '/etc/containers/storage.conf'
systemd_unit_path = '/run/systemd/system'

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
    # registry will be handled below
    if 'registry' in default_values:
        del default_values['registry']
    container = dict_merge(default_values, container)

    # Merge per-container default values
    if 'name' in container:
        default_values = defaults(base + ['name'])
        if 'port' in default_values:
            del default_values['port']
        if 'volume' in default_values:
            del default_values['volume']
        for name in container['name']:
            container['name'][name] = dict_merge(default_values, container['name'][name])

            # T5047: Any container related configuration changed? We only
            # wan't to restart the required containers and not all of them ...
            tmp = is_node_changed(conf, base + ['name', name])
            if tmp:
                if 'container_restart' not in container:
                    container['container_restart'] = [name]
                else:
                    container['container_restart'].append(name)

            # XXX: T2665: we can not safely rely on the defaults() when there are
            # tagNodes in place, it is better to blend in the defaults manually.
            if 'port' in container['name'][name]:
                for port in container['name'][name]['port']:
                    default_values_port = defaults(base + ['name', 'port'])
                    container['name'][name]['port'][port] = dict_merge(
                        default_values_port, container['name'][name]['port'][port])
            # XXX: T2665: we can not safely rely on the defaults() when there are
            # tagNodes in place, it is better to blend in the defaults manually.
            if 'volume' in container['name'][name]:
                for volume in container['name'][name]['volume']:
                    default_values_volume = defaults(base + ['name', 'volume'])
                    container['name'][name]['volume'][volume] = dict_merge(
                        default_values_volume, container['name'][name]['volume'][volume])

    # registry is a tagNode with default values - merge the list from
    # default_values['registry'] into the tagNode variables
    if 'registry' not in container:
        container.update({'registry' : {}})
        default_values = defaults(base)
        for registry in default_values['registry'].split():
            tmp = {registry : {}}
            container['registry'] = dict_merge(tmp, container['registry'])

    # Delete container network, delete containers
    tmp = node_changed(conf, base + ['network'])
    if tmp: container.update({'network_remove' : tmp})

    tmp = node_changed(conf, base + ['name'])
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
            if run(f'podman image exists {image}') != 0 and 'auto_pull' not in container_config:
                Warning(f'Image "{image}" used in container "{name}" does not exist '\
                        f'locally. Please use "add container image {image}" to add it '\
                        f'to the system or add auto-pull in container "{name}"! '\
                        f'Container "{name}" will not be started!')

            if 'network' in container_config:
                if len(container_config['network']) > 1:
                    raise ConfigError(f'Only one network can be specified for container "{name}"!')

                # Check if the specified container network exists
                network_name = list(container_config['network'])[0]
                if network_name not in container.get('network', {}):
                    raise ConfigError(f'Container network "{network_name}" does not exist!')

                if 'address' in container_config['network'][network_name]:
                    cnt_ipv4 = 0
                    cnt_ipv6 = 0
                    for address in container_config['network'][network_name]['address']:
                        network = None
                        if is_ipv4(address):
                            network = [x for x in container['network'][network_name]['prefix'] if is_ipv4(x)][0]
                            cnt_ipv4 += 1
                        elif is_ipv6(address):
                            network = [x for x in container['network'][network_name]['prefix'] if is_ipv6(x)][0]
                            cnt_ipv6 += 1

                        # Specified container IP address must belong to network prefix
                        if ip_address(address) not in ip_network(network):
                            raise ConfigError(f'Used container address "{address}" not in network "{network}"!')

                        # We can not use the first IP address of a network prefix as this is used by podman
                        if ip_address(address) == ip_network(network)[1]:
                            raise ConfigError(f'IP address "{address}" can not be used for a container, '\
                                              'reserved for the container engine!')

                    if cnt_ipv4 > 1 or cnt_ipv6 > 1:
                        raise ConfigError(f'Only one IP address per address family can be used for '\
                                          f'container "{name}". {cnt_ipv4} IPv4 and {cnt_ipv6} IPv6 address(es)!')

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

            if 'port' in container_config:
                for tmp in container_config['port']:
                    if not {'source', 'destination'} <= set(container_config['port'][tmp]):
                        raise ConfigError(f'Both "source" and "destination" must be specified for a port mapping!')

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

            # Verify VRF exists
            verify_vrf(network_config)

    # A network attached to a container can not be deleted
    if {'network_remove', 'name'} <= set(container):
        for network in container['network_remove']:
            for container, container_config in container['name'].items():
                if 'network' in container_config and network in container_config['network']:
                    raise ConfigError(f'Can not remove network "{network}", used by container "{container}"!')

    if 'registry' in container:
        for registry, registry_config in container['registry'].items():
            if 'authentication' not in registry_config:
                continue
            if not {'username', 'password'} <= set(registry_config['authentication']):
                raise ConfigError('If registry username or or password is defined, so must be the other!')

    return None

def generate_run_arguments(name, container_config):
    image = container_config['image']
    memory = container_config['memory']
    shared_memory = container_config['shared_memory']
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
            env_opt += f" --env \"{k}={v['value']}\""

    hostname = ''
    if 'host_name' in container_config:
        hostname = container_config['host_name']
        hostname = f'--hostname {hostname}'

    # Publish ports
    port = ''
    if 'port' in container_config:
        protocol = ''
        for portmap in container_config['port']:
            protocol = container_config['port'][portmap]['protocol']
            sport = container_config['port'][portmap]['source']
            dport = container_config['port'][portmap]['destination']
            port += f' --publish {sport}:{dport}/{protocol}'

    # Bind volume
    volume = ''
    if 'volume' in container_config:
        for vol, vol_config in container_config['volume'].items():
            svol = vol_config['source']
            dvol = vol_config['destination']
            mode = vol_config['mode']
            prop = vol_config['propagation']
            volume += f' --volume {svol}:{dvol}:{mode},{prop}'

    container_base_cmd = f'--detach --interactive --tty --replace {cap_add} ' \
                         f'--memory {memory}m --shm-size {shared_memory}m --memory-swap 0 --restart {restart} ' \
                         f'--name {name} {hostname} {device} {port} {volume} {env_opt}'

    entrypoint = ''
    if 'entrypoint' in container_config:
        # it needs to be json-formatted with single quote on the outside
        entrypoint = json_write(container_config['entrypoint'].split()).replace('"', "&quot;")
        entrypoint = f'--entrypoint &apos;{entrypoint}&apos;'

    hostname = ''
    if 'host_name' in container_config:
        hostname = container_config['host_name']
        hostname = f'--hostname {hostname}'

    command = ''
    if 'command' in container_config:
        command = container_config['command'].strip()

    command_arguments = ''
    if 'arguments' in container_config:
        command_arguments = container_config['arguments'].strip()

    if 'allow_host_networks' in container_config:
        return f'{container_base_cmd} --net host {entrypoint} {image} {command} {command_arguments}'.strip()

    ip_param = ''
    networks = ",".join(container_config['network'])
    for network in container_config['network']:
        if 'address' not in container_config['network'][network]:
            continue
        for address in container_config['network'][network]['address']:
            if is_ipv6(address):
                ip_param += f' --ip6 {address}'
            else:
                ip_param += f' --ip {address}'

    return f'{container_base_cmd} --net {networks} {ip_param} {entrypoint} {image} {command} {command_arguments}'.strip()

def generate(container):
    # bail out early - looks like removal from running config
    if not container:
        for file in [config_containers, config_registry, config_storage]:
            if os.path.exists(file):
                os.unlink(file)
        return None

    if 'network' in container:
        for network, network_config in container['network'].items():
            tmp = {
                'name': network,
                'id' : sha256(f'{network}'.encode()).hexdigest(),
                'driver': 'bridge',
                'network_interface': f'pod-{network}',
                'subnets': [],
                'ipv6_enabled': False,
                'internal': False,
                'dns_enabled': True,
                'ipam_options': {
                    'driver': 'host-local'
                }
            }
            for prefix in network_config['prefix']:
                net = {'subnet' : prefix, 'gateway' : inc_ip(prefix, 1)}
                tmp['subnets'].append(net)

                if is_ipv6(prefix):
                    tmp['ipv6_enabled'] = True

            write_file(f'/etc/containers/networks/{network}.json', json_write(tmp, indent=2))

    if 'registry' in container:
        cmd = f'podman logout --all'
        rc, out = rc_cmd(cmd)
        if rc != 0:
            raise ConfigError(out)

        for registry, registry_config in container['registry'].items():
            if 'disable' in registry_config:
                continue
            if 'authentication' in registry_config:
                if {'username', 'password'} <= set(registry_config['authentication']):
                    username = registry_config['authentication']['username']
                    password = registry_config['authentication']['password']
                    cmd = f'podman login --username {username} --password {password} {registry}'
                    rc, out = rc_cmd(cmd)
                    if rc != 0:
                        raise ConfigError(out)

    render(config_containers, 'container/containers.conf.j2', container)
    render(config_registry, 'container/registries.conf.j2', container)
    render(config_storage, 'container/storage.conf.j2', container)

    if 'name' in container:
        for name, container_config in container['name'].items():
            if 'disable' in container_config:
                continue

            file_path = os.path.join(systemd_unit_path, f'vyos-container-{name}.service')
            run_args = generate_run_arguments(name, container_config)
            render(file_path, 'container/systemd-unit.j2', {'name': name, 'run_args': run_args,},
                   formater=lambda _: _.replace("&quot;", '"').replace("&apos;", "'"))

    return None

def apply(container):
    # Delete old containers if needed. We can't delete running container
    # Option "--force" allows to delete containers with any status
    if 'container_remove' in container:
        for name in container['container_remove']:
            file_path = os.path.join(systemd_unit_path, f'vyos-container-{name}.service')
            call(f'systemctl stop vyos-container-{name}.service')
            if os.path.exists(file_path):
                os.unlink(file_path)

    call('systemctl daemon-reload')

    # Delete old networks if needed
    if 'network_remove' in container:
        for network in container['network_remove']:
            call(f'podman network rm {network} >/dev/null 2>&1')

    # Add container
    disabled_new = False
    if 'name' in container:
        for name, container_config in container['name'].items():
            image = container_config['image']

            if run(f'podman image exists {image}') != 0 and 'auto_pull' not in container_config:
                # container image does not exist locally - user already got
                # informed by a WARNING in verify() - bail out early
                continue

            if 'disable' in container_config:
                # check if there is a container by that name running
                tmp = _cmd('podman ps -a --format "{{.Names}}"')
                if name in tmp:
                    file_path = os.path.join(systemd_unit_path, f'vyos-container-{name}.service')
                    call(f'systemctl stop vyos-container-{name}.service')
                    if os.path.exists(file_path):
                        disabled_new = True
                        os.unlink(file_path)
                continue

            if 'container_restart' in container and name in container['container_restart']:
                cmd(f'systemctl restart vyos-container-{name}.service')

    if disabled_new:
        call('systemctl daemon-reload')

    # Start network and assign it to given VRF if requested. this can only be done
    # after the containers got started as the podman network interface will
    # only be enabled by the first container and yet I do not know how to enable
    # the network interface in advance
    if 'network' in container:
        for network, network_config in container['network'].items():
            network_name = f'pod-{network}'
            # T5147: Networks are started only as soon as there is a consumer.
            # If only a network is created in the first place, no need to assign
            # it to a VRF as there's no consumer, yet.
            if os.path.exists(f'/sys/class/net/{network_name}'):
                tmp = Interface(network_name)
                tmp.set_vrf(network_config.get('vrf', ''))

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
