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
import re
from pathlib import Path

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.util import call
from vyos.util import read_file
from vyos.util import write_file
from vyos.template import render
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

by_bus_dir = '/dev/serial/by-bus'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'console']

    # retrieve configuration at once
    console = conf.get_config_dict(base, get_first_key=True)

    # bail out early if no serial console is configured
    if 'device' not in console:
        return console

    # convert CLI values to system values
    default_values = defaults(base + ['device'])
    for device, device_config in console['device'].items():
        if 'speed' not in device_config and device.startswith('hvc'):
            # XEN console has a different default console speed
            console['device'][device]['speed'] = 38400
        else:
            # Merge in XML defaults - the proper way to do it
            console['device'][device] = dict_merge(default_values,
                                                   console['device'][device])

    return console

def verify(console):
    if not console or 'device' not in console:
        return None

    for device in console['device']:
        if device.startswith('usb'):
            # It is much easiert to work with the native ttyUSBn name when using
            # getty, but that name may change across reboots - depending on the
            # amount of connected devices. We will resolve the fixed device name
            # to its dynamic device file - and create a new dict entry for it.
            by_bus_device = f'{by_bus_dir}/{device}'
            # If the device name still starts with usbXXX no matching tty was found
            # and it can not be used as a serial interface
            if not os.path.isdir(by_bus_dir) or not os.path.exists(by_bus_device):
                raise ConfigError(f'Device {device} does not support beeing used as tty')

    return None

def generate(console):
    base_dir = '/run/systemd/system'
    # Remove all serial-getty configuration files in advance
    for root, dirs, files in os.walk(base_dir):
        for basename in files:
            if 'serial-getty' in basename:
                call(f'systemctl stop {basename}')
                os.unlink(os.path.join(root, basename))

    if not console or 'device' not in console:
        return None

    # replace keys in the config for ttyUSB items to use them in `apply()` later
    for device in console['device'].copy():
        if device.startswith('usb'):
            # It is much easiert to work with the native ttyUSBn name when using
            # getty, but that name may change across reboots - depending on the
            # amount of connected devices. We will resolve the fixed device name
            # to its dynamic device file - and create a new dict entry for it.
            by_bus_device = f'{by_bus_dir}/{device}'
            if os.path.isdir(by_bus_dir) and os.path.exists(by_bus_device):
                device_updated = os.path.basename(os.readlink(by_bus_device))

                # replace keys in the config to use them in `apply()` later
                console['device'][device_updated] = console['device'][device]
                del console['device'][device]
            else:
                raise ConfigError(f'Device {device} does not support beeing used as tty')

    for device, device_config in console['device'].items():
        config_file = base_dir + f'/serial-getty@{device}.service'
        Path(f'{base_dir}/getty.target.wants').mkdir(exist_ok=True)
        getty_wants_symlink = base_dir + f'/getty.target.wants/serial-getty@{device}.service'

        render(config_file, 'getty/serial-getty.service.j2', device_config)
        os.symlink(config_file, getty_wants_symlink)

    # GRUB
    # For existing serial line change speed (if necessary)
    # Only applys to ttyS0
    if 'ttyS0' not in console['device']:
        return None

    speed = console['device']['ttyS0']['speed']
    grub_config = '/boot/grub/grub.cfg'
    if not os.path.isfile(grub_config):
        return None

    lines = read_file(grub_config).split('\n')
    p = re.compile(r'^(.* console=ttyS0),[0-9]+(.*)$')
    write = False
    newlines = []
    for line in lines:
        if line.startswith('serial --unit'):
            newline = f'serial --unit=0 --speed={speed}'
        elif p.match(line):
            newline = '{},{}{}'.format(p.search(line)[1], speed, p.search(line)[2])
        else:
            newline = line

        if newline != line:
            write = True

        newlines.append(newline)
    newlines.append('')

    if write:
        write_file(grub_config, '\n'.join(newlines))

    return None

def apply(console):
    # Reset screen blanking
    call('/usr/bin/setterm -blank 0 -powersave off -powerdown 0 -term linux </dev/tty1 >/dev/tty1 2>&1')
    # Reload systemd manager configuration
    call('systemctl daemon-reload')

    if not console:
        return None

    if 'powersave' in console.keys():
        # Configure screen blank powersaving on VGA console
        call('/usr/bin/setterm -blank 15 -powersave powerdown -powerdown 60 -term linux </dev/tty1 >/dev/tty1 2>&1')

    # Start getty process on configured serial interfaces
    for device in console['device']:
        # Only start console if it exists on the running system. If a user
        # detaches a USB serial console and reboots - it should not fail!
        if os.path.exists(f'/dev/{device}'):
            call(f'systemctl restart serial-getty@{device}.service')

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
