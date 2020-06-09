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
from vyos.template import render
from vyos import ConfigError, airbag
airbag.enable()

by_bus_dir = '/dev/serial/by-bus'

def get_config():
    conf = Config()
    base = ['system', 'console']

    # retrieve configuration at once
    console = conf.get_config_dict(base)

    # bail out early if no serial console is configured
    if 'device' not in console.keys():
        return console

    # convert CLI values to system values
    for device in console['device'].keys():
        # no speed setting has been configured - use default value
        if not 'speed' in console['device'][device].keys():
            tmp = { 'speed': '' }
            if device.startswith('hvc'):
                tmp['speed'] = 38400
            else:
                tmp['speed'] = 115200

            console['device'][device].update(tmp)

        if device.startswith('usb'):
            # It is much easiert to work with the native ttyUSBn name when using
            # getty, but that name may change across reboots - depending on the
            # amount of connected devices. We will resolve the fixed device name
            # to its dynamic device file - and create a new dict entry for it.
            by_bus_device = f'{by_bus_dir}/{device}'
            if os.path.isdir(by_bus_dir) and os.path.exists(by_bus_device):
                tmp = os.path.basename(os.readlink(by_bus_device))
                # updating the dict must come as last step in the loop!
                console['device'][tmp] = console['device'].pop(device)

    return console

def verify(console):
    return None

def generate(console):
    base_dir = '/etc/systemd/system'
    # Remove all serial-getty configuration files in advance
    for root, dirs, files in os.walk(base_dir):
        for basename in files:
            if 'serial-getty' in basename:
                call(f'systemctl stop {basename}')
                os.unlink(os.path.join(root, basename))

    for device in console['device'].keys():
        config_file = base_dir + f'/serial-getty@{device}.service'
        render(config_file, 'getty/serial-getty.service.tmpl', console['device'][device])

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
        # Only start console if it exists on the running system. If a user
        # detaches a USB serial console and reboots - it should not fail!
        if os.path.exists(f'/dev/{device}'):
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
