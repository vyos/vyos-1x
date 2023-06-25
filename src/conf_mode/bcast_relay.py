#!/usr/bin/env python3
#
# Copyright (C) 2017-2022 VyOS maintainers and contributors
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

from glob import glob
from netifaces import interfaces
from sys import exit

from vyos.config import Config
from vyos.util import call
from vyos.template import render
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file_base = r'/etc/default/udp-broadcast-relay'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'broadcast-relay']

    relay = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    return relay

def verify(relay):
    if not relay or 'disabled' in relay:
        return None

    for instance, config in relay.get('id', {}).items():
        # we don't have to check this instance when it's disabled
        if 'disabled' in config:
            continue

        # we certainly require a UDP port to listen to
        if 'port' not in config:
            raise ConfigError(f'Port number mandatory for udp broadcast relay "{instance}"')

        # if only oone interface is given it's a string -> move to list
        if isinstance(config.get('interface', []), str):
            config['interface'] = [ config['interface'] ]
        # Relaying data without two interface is kinda senseless ...
        if len(config.get('interface', [])) < 2 or len(config.get('interface', [])) > 2:
            raise ConfigError('Only two interfaces are required for udp broadcast relay "{instance}"')

        for interface in config.get('interface', []):
            if interface not in interfaces():
                raise ConfigError('Interface "{interface}" does not exist!')

    return None

def generate(relay):
    if not relay or 'disabled' in relay:
        return None

    for config in glob(config_file_base + '*'):
        os.remove(config)

    for instance, config in relay.get('id').items():
        # we don't have to check this instance when it's disabled
        if 'disabled' in config:
            continue

        config['instance'] = instance
        render(config_file_base + instance, 'bcast-relay/udp-broadcast-relay.j2',
               config)

    return None

def apply(relay):
    # first stop all running services
    call('systemctl stop udp-broadcast-relay@*.service')

    if not relay or 'disable' in relay:
        return None

    # start only required service instances
    for instance, config in relay.get('id').items():
        # we don't have to check this instance when it's disabled
        if 'disabled' in config:
            continue

        call(f'systemctl start udp-broadcast-relay@{instance}.service')

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
