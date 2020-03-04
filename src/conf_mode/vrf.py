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

from sys import exit
from copy import deepcopy
from vyos.config import Config
from vyos import ConfigError
from vyos import vrf


# https://github.com/torvalds/linux/blob/master/Documentation/networking/vrf.txt


def sysctl(name, value):
    os.system('sysctl -wq {}={}'.format(name, value))

def interfaces_with_vrf (match, effective):
    matched = []
    config = Config()
    section = config.get_config_dict('interfaces', effective)
    for type in section:
        interfaces = section[type]
        for name in interfaces:
            interface = interfaces[name]
            if 'vrf' in interface:
                v = interface.get('vrf', '')
                if v == match:
                    matched.append(name)
    return matched

def get_config():
    command = {
        'bind':{},
        'vrf':[],
        'int': {},  # per vrf name list of interfaces which will have it
    }

    config = Config()

    old = {}
    new = {}

    if config.exists_effective('vrf'):
        old = deepcopy(config.get_config_dict('vrf', True))

    if config.exists('vrf'):
        new = deepcopy(config.get_config_dict('vrf', False))

    integer = lambda _: '1' if _ else '0'
    command['bind']['ipv4'] = integer('ipv4' not in new.get('disable-bind-to-all', {}))
    command['bind']['ipv6'] = integer('ipv6' not in new.get('disable-bind-to-all', {}))

    old_names = old.get('name', [])
    new_names = new.get('name', [])
    all_names = list(set(old_names) | set(new_names))
    del_names = list(set(old_names).difference(new_names))
    mod_names = list(set(old_names).intersection(new_names))
    add_names = list(set(new_names).difference(old_names))

    for name in all_names:
        v = {
            'name': name,
            'action': 'miss',
            'table': -1,
            'check': -1,
        }

        if name in new_names:
            v['table'] = new.get('name', {}).get(name, {}).get('table', -1)
            v['check'] = old.get('name', {}).get(name, {}).get('table', -1)

        if name in add_names:
            v['action'] = 'add'
        elif name in del_names:
            v['action'] = 'delete'
        elif name in mod_names:
            if v['table'] != -1:
                if v['check'] == -1:
                    v['action'] = 'add'
            else: 
                v['action'] = 'modify'

        command['vrf'].append(v)

    for v in vrf.list_vrfs():
        name = v['ifname']
        command['int'][name] = interfaces_with_vrf(name,False)

    return command


def verify(command):
    for v in command['vrf']:
        action = v['action']
        name = v['name']
        if action == 'modify' and v['table'] != v['check']:
            raise ConfigError(f'set vrf name {name}: modification of vrf table is not supported yet')
        if action == 'delete' and name in command['int']:
            interface = ', '.join(command['int'][name])
            if interface:
                raise ConfigError(f'delete vrf name {name}: can not delete vrf as it is used on {interface}')

    return command


def generate(command):
    return command


def apply(command):
    # set the default VRF global behaviour
    sysctl('net.ipv4.tcp_l3mdev_accept', command['bind']['ipv4'])
    sysctl('net.ipv4.udp_l3mdev_accept', command['bind']['ipv4'])

    errors = []
    for v in command['vrf']:
        name = v['name']
        action = v['action']
        table = v['table']

        errors.append(f'could not {action} vrf {name}')

        if action == 'miss':
            continue

        if action == 'delete':
            if os.system(f'sudo ip link delete dev {name}'):
                continue
            errors.pop()
            continue

        if action == 'modify':
            # > uname -a
            # Linux vyos 4.19.101-amd64-vyos #1 SMP Sun Feb 2 10:18:07 UTC 2020 x86_64 GNU/Linux
            # > ip link add my-vrf type vrf table 100
            # > ip link set my-vrf type vrf table 200
            # RTNETLINK answers: Operation not supported
            # so require to remove vrf and change all existing the interfaces

            if os.system(f'ip link delete dev {name}'):
                continue
            action = 'add'

        if action == 'add':
            commands = [
                f'ip link add {name} type vrf table {table}',
                f'ip link set dev {name} up',
                f'ip -4 rule add oif {name} lookup {table}',
                f'ip -4 rule add iif {name} lookup {table}',
                f'ip -6 rule add oif {name} lookup {table}',
                f'ip -6 rule add iif {name} lookup {table}',
            ]

            for command in commands:
                if os.system(command):
                    errors[-1] += ' ('+command+')'
                    continue
            errors.pop()

    if errors:
        raise ConfigError(', '.join(errors))

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
