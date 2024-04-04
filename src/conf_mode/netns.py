#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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

from vyos.config import Config
from vyos.configdict import node_changed
from vyos.utils.process import call
from vyos.utils.dict import dict_search
from vyos import ConfigError
from vyos import airbag
airbag.enable()


def netns_interfaces(c, match):
    """
    get NETNS bound interfaces
    """
    matched = []
    old_level = c.get_level()
    c.set_level(['interfaces'])
    section = c.get_config_dict([], get_first_key=True)
    for type in section:
        interfaces = section[type]
        for name in interfaces:
            interface = interfaces[name]
            if 'netns' in interface:
                v = interface.get('netns', '')
                if v == match:
                    matched.append(name)

    c.set_level(old_level)
    return matched

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['netns']
    netns = conf.get_config_dict(base, get_first_key=True,
                                       no_tag_node_value_mangle=True)

    # determine which NETNS has been removed
    for name in node_changed(conf, base + ['name']):
        if 'netns_remove' not in netns:
            netns.update({'netns_remove' : {}})

        netns['netns_remove'][name] = {}
        # get NETNS bound interfaces
        interfaces = netns_interfaces(conf, name)
        if interfaces: netns['netns_remove'][name]['interface'] = interfaces

    return netns

def verify(netns):
    # ensure NETNS is not assigned to any interface
    if 'netns_remove' in netns:
        for name, config in netns['netns_remove'].items():
            if 'interface' in config:
                raise ConfigError(f'Can not remove network namespace "{name}", it '\
                                  f'still has member interfaces!')

    if 'name' in netns:
        for name, config in netns['name'].items():
            # no tests (yet)
            pass

    return None

def generate(netns):
    if not netns:
        return None

    return None


def apply(netns):

    for tmp in (dict_search('netns_remove', netns) or []):
        if os.path.isfile(f'/run/netns/{tmp}'):
            call(f'ip netns del {tmp}')

    if 'name' in netns:
        for name, config in netns['name'].items():
            if not os.path.isfile(f'/run/netns/{name}'):
                call(f'ip netns add {name}')

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
