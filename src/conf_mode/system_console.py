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
from vyos.util import call
from vyos import ConfigError, airbag
airbag.enable()

serial_getty_file = '/lib/systemd/system/serial-getty@.service'

def get_config():
    conf = Config()
    base = ['system', 'console']

    if not conf.exists(base):
        return None

    # retrieve configuration at once
    console = conf.get_config_dict(base)

    # set default values
    if 'device' in console.keys():
        for device in console['device'].keys():
            # no speed setting has been configured - use default value
            if not 'speed' in console['device'][device].keys():
                tmp = { 'speed': '' }
                if device.startswith('hvc'):
                    tmp['speed'] = 38400
                else:
                    tmp['speed'] = 115200

                console['device'][device].update(tmp)

    return console

def verify(console):
    if not os.path.isfile(serial_getty_file):
        raise ConfigError(f'Could not open: {serial_getty_file}')

    return None

def generate(console):
    base_dir = '/etc/systemd/system'
    # Remove all serial-getty configuration files in advance
    for root, dirs, files in os.walk(base_dir):
        for basename in files:
            if 'serial-getty' in basename:
                call(f'systemctl stop {basename}')
                os.unlink(os.path.join(root, basename))

    # bail out early if serial device is not configured
    if not console or 'device' not in console.keys():
        return None

    for device in console['device'].keys():
        serial_getty_device_file = f'{base_dir}/serial-getty@{device}.service'
        serial_getty_wants_file = f'{base_dir}/getty.target.wants/serial-getty@{device}.service'

        with open(serial_getty_file, 'r') as f:
            tmp = f.read()
        tmp = tmp.replace('115200,38400,9600', str(console['device'][device]['speed']))

        with open(serial_getty_device_file, 'w') as f:
            f.write(tmp)

    # Reload systemd manager configuration
    call('systemctl daemon-reload')
    return None

def apply(console):
    # bail out early
    if not console:
        call( '/usr/bin/setterm -blank 0 -powersave off -powerdown 0 -term linux </dev/console >/dev/console 2>&1')
        return None

    # Configure screen blank powersaving on VGA console
    if 'powersave' in console.keys():
        call('/usr/bin/setterm -blank 15 -powersave powerdown -powerdown 60 -term linux </dev/console >/dev/console 2>&1')
    else:
        call( '/usr/bin/setterm -blank 0 -powersave off -powerdown 0 -term linux </dev/console >/dev/console 2>&1')

    # Start getty process on configured serial interfaces
    for device in console['device'].keys():
        call(f'systemctl start serial-getty@{device}.service')

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
