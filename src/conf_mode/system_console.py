#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
import platform
from pathlib import Path

from vyos.base import Warning
from vyos.config import Config
from vyos.utils.process import call
from vyos.utils.serial import restart_login_consoles
from vyos.utils.serial import is_tty
from vyos.system import grub_util
from vyos.template import render
from vyos import ConfigError
from vyos import airbag
from vyos import flavor
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

    for device, device_config in console['device'].items():
        if 'speed' not in device_config and device.startswith('hvc'):
            # XEN console has a different default console speed
            console['device'][device]['speed'] = 38400

    console = conf.merge_defaults(console, recursive=True)

    return console

def verify(console):
    if not console or 'device' not in console:
        return None

    kernel_consoles: list = []
    for device, device_config in console['device'].items():
        if device.startswith('usb'):
            # It is much easiert to work with the native ttyUSBn name when using
            # getty, but that name may change across reboots - depending on the
            # amount of connected devices. We will resolve the fixed device name
            # to its dynamic device file - and create a new dict entry for it.
            by_bus_device = f'{by_bus_dir}/{device}'
            # If the device name still starts with usbXXX no matching tty was found
            # and it can not be used as a serial interface
            if not os.path.isdir(by_bus_dir) or not os.path.exists(by_bus_device):
                raise ConfigError(f'Device {device} does not support being used as tty')
        if not is_tty(device, warning=True):
            Warning(f'Device "{device}" used for console is not a TTY!')
        if 'kernel' in device_config:
            kernel_consoles.append(device)

    if len(kernel_consoles) > 1:
        raise ConfigError('Only one device can be used as Kernel output console!')

    return None

def generate(console):
    base_dir = '/run/systemd/system'
    # Remove all serial-getty configuration files in advance
    for root, dirs, files in os.walk(base_dir):
        for basename in files:
            if 'serial-getty' in basename:
                os.unlink(os.path.join(root, basename))

    # PSL: Try to get console from the flavor.json files before defaulting
    try:
        default_tty_console = flavor.get_image_serial_console()
    except Exception:
        if platform.machine() == 'aarch64':
            # PSL: prefer ttyS0/115200 on arm64.
            default_tty_console = ('ttyS', '0', '115200')
        else:
            # Define a default console on a tty framebuffer
            default_tty_console = ('tty', '0', '')

    if not console or 'device' not in console:
        grub_util.update_serial_console(*default_tty_console)
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
                raise ConfigError(f'Device {device} does not support being used as tty')

    for device, device_config in console['device'].items():
        # Do not render getty configuration if specified device is not a TTY.
        if not is_tty(device):
            continue
        config_file = base_dir + f'/serial-getty@{device}.service'
        Path(f'{base_dir}/getty.target.wants').mkdir(exist_ok=True)
        getty_wants_symlink = base_dir + f'/getty.target.wants/serial-getty@{device}.service'

        render(config_file, 'getty/serial-getty.service.j2', device_config)
        os.symlink(config_file, getty_wants_symlink)

        if 'kernel' in device_config:
            # get console type ("ttyS" or "ttyAMA") from device (e.g. "ttyS0")
            console_type = device.rstrip('0123456789')
            console_num = device[len(console_type):]
            default_tty_console = (console_type, console_num, device_config['speed'])

    grub_util.update_serial_console(*default_tty_console)
    return None

def apply(console):
    # Reset screen blanking
    call('/usr/bin/setterm -blank 0 -powersave off -powerdown 0 -term linux </dev/tty1 >/dev/tty1 2>&1')

    # Service control moved to vyos.utils.serial to unify checks and prompts.
    # If users are connected, we want to show an informational message on completing
    # the process, but not halt configuration processing with an interactive prompt.
    restart_login_consoles(prompt_user=False, quiet=False)

    if not console:
        return None

    if 'powersave' in console.keys():
        # Configure screen blank powersaving on VGA console
        call('/usr/bin/setterm -blank 15 -powersave powerdown -powerdown 60 -term linux </dev/tty1 >/dev/tty1 2>&1')

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
