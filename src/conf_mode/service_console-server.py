#!/usr/bin/env python3
#
# Copyright (C) 2018-2021 VyOS maintainers and contributors
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
from psutil import process_iter

from vyos.config import Config
from vyos.template import render
from vyos.utils.process import call
from vyos import ConfigError

config_file = '/run/conserver/conserver.cf'
dropbear_systemd_file = '/run/systemd/system/dropbear@{port}.service.d/override.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'console-server']

    # Retrieve CLI representation as dictionary
    proxy = conf.get_config_dict(base, key_mangling=('-', '_'),
                                 get_first_key=True)
    # The retrieved dictionary will look something like this:
    #
    # {'device': {'usb0b2.4p1.0': {'speed': '9600'},
    #             'usb0b2.4p1.1': {'data_bits': '8',
    #                              'parity': 'none',
    #                              'speed': '115200',
    #                              'stop_bits': '2'}}}

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    proxy = conf.merge_defaults(proxy, recursive=True)

    return proxy

def verify(proxy):
    if not proxy:
        return None

    aliases = []
    processes = process_iter(['name', 'cmdline'])
    if 'device' in proxy:
        for device, device_config in proxy['device'].items():
            for process in processes:
                if 'agetty' in process.name() and device in process.cmdline():
                    raise ConfigError(f'Port "{device}" already provides a '\
                                      'console used by "system console"!')

            if 'speed' not in device_config:
                raise ConfigError(f'Port "{device}" requires speed to be set!')

            if 'ssh' in device_config and 'port' not in device_config['ssh']:
                raise ConfigError(f'Port "{device}" requires SSH port to be set!')

            if 'alias' in device_config:
                if device_config['alias'] in aliases:
                    raise ConfigError("Console aliases must be unique")
                else:
                    aliases.append(device_config['alias'])

    return None

def generate(proxy):
    if not proxy:
        return None

    render(config_file, 'conserver/conserver.conf.j2', proxy)
    if 'device' in proxy:
        for device, device_config in proxy['device'].items():
            if 'ssh' not in device_config:
                continue

            tmp = {
                'device' : device,
                'port' : device_config['ssh']['port'],
            }
            render(dropbear_systemd_file.format(**tmp),
                   'conserver/dropbear@.service.j2', tmp)

    return None

def apply(proxy):
    call('systemctl daemon-reload')
    call('systemctl stop dropbear@*.service conserver-server.service')

    if not proxy:
        if os.path.isfile(config_file):
            os.unlink(config_file)
        return None

    call('systemctl restart conserver-server.service')

    if 'device' in proxy:
        for device, device_config in proxy['device'].items():
            if 'ssh' not in device_config:
                continue
            port = device_config['ssh']['port']
            call(f'systemctl restart dropbear@{port}.service')

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
