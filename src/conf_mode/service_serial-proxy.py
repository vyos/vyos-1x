#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
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
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.util import call
from vyos import ConfigError

config_file = r'/run/conserver/conserver.cf'

# Default values are necessary until the implementation of T2588 is completed
default_values = {
    'data_bits': '8',
    'parity': 'none',
    'stop_bits': '1'
}

def get_config():
    conf = Config()
    base = ['service', 'serial-proxy']

    if not conf.exists(base):
        return None

    # Retrieve CLI representation as dictionary
    proxy = conf.get_config_dict(base, key_mangling=('-', '_'))
    # The retrieved dictionary will look something like this:
    #
    # {'device': {'usb0b2.4p1.0': {'speed': '9600'},
    #             'usb0b2.4p1.1': {'data_bits': '8',
    #                              'parity': 'none',
    #                              'speed': '115200',
    #                              'stop_bits': '2'}}}

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    for device in proxy['device'].keys():
        tmp = dict_merge(default_values, proxy['device'][device])
        proxy['device'][device] = tmp

    return proxy

def verify(proxy):
    if not proxy:
        return None

    for tmp in proxy['device']:
        device = proxy['device'][tmp]
        if not device['speed']:
            raise ConfigError(f'Serial port speed must be defined for "{tmp}"!')

        if 'ssh' in device.keys():
            if 'port' not in device['ssh'].keys():
                raise ConfigError(f'SSH port must be defined for "{tmp}"!')

    return None

def generate(proxy):
    if not proxy:
        return None

    render(config_file, 'conserver/conserver.conf.tmpl', proxy)
    return None

def apply(proxy):
    call('systemctl stop conserver-server.service')
    call('systemctl stop dropbear@*.service')

    if not proxy:
        if os.path.isfile(config_file):
            os.unlink(config_file)
        return None

    call('systemctl restart conserver-server.service')

    for device in proxy['device']:
        if 'ssh' in proxy['device'][device].keys():
            call('systemctl restart dropbear@{device}.service')

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
