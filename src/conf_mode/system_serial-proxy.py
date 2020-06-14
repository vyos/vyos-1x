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

from copy import deepcopy
from sys import exit

from vyos.config import Config
from vyos.template import render
from vyos.util import call
from vyos import ConfigError

config_file = r'/run/ser2net/ser2net.conf'

default_config_data = {
    'devices': [],
}

def get_config():
    proxy = deepcopy(default_config_data)
    conf = Config()
    base = ['service', 'serial-proxy']

    if not conf.exists(base):
        return None
    else:
        conf.set_level(base)

    for serial_port in conf.list_nodes(['device']):
        conf.set_level(base + ['device', serial_port])
        serial = {
            'data_bits': '',
            'parity': '',
            'port': '',
            'serial_port': '/dev/serial/by-bus/' + serial_port,
            'speed': '',
            'stop_bits': '',
            'timeout': '600'
        }

        if conf.exists(['data-bits']):
            serial['data_bits'] = conf.return_value(['data-bits'])

        if conf.exists(['stop-bits']):
            serial['stop_bits'] = conf.return_value(['stop-bits'])

        if conf.exists(['parity']):
            serial['parity'] = conf.return_value(['parity'])

        if conf.exists(['port']):
            serial['port'] = conf.return_value(['port'])

        if conf.exists(['speed']):
            serial['speed'] = conf.return_value(['speed'])

        proxy['devices'].append(serial)

    return proxy

def verify(proxy):
    if not proxy:
        return None

    for device in proxy['devices']:
        if not os.path.exists('{serial_port}'.format(**device)):
            raise ConfigError('Serial interface "{serial_port} does not exist"'
                              .format(**device))

        for key in ['data_bits', 'parity', 'port', 'speed', 'stop_bits']:
            if not device[key]:
                value = key.replace('_','-')
                raise ConfigError(f'{value} option must be defined!')

    return None

def generate(proxy):
    if not proxy:
        return None

    render(config_file, 'ser2net/ser2net.conf.tmpl', proxy)
    return None

def apply(proxy):
    if not proxy:
        call('systemctl stop ser2net.service')
        if os.path.isfile(config_file):
            os.unlink(config_file)

        return None

    call('systemctl start ser2net.service')
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
