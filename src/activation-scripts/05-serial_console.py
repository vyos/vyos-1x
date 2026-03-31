# Copyright (C) VyOS Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

import re

from typing import Optional
from typing import Tuple

from vyos.configtree import ConfigTree
from vyos.utils.file import read_file
from vyos.system.image import is_live_boot

base = ['system', 'console', 'device']

def get_kernel_serial_console() -> Tuple[Optional[str], Optional[str]]:
    """
    Extract the serial console device and speed setting from the kernel
    command line.
    """
    device = speed = None
    CMDLINE_CONSOLE_RE = re.compile(
        r'(?:^|\s)console=(?P<device>tty(?:S|AMA)\d+),(?P<speed>\d+)(?=\s|$)'
    )
    kernel_cmdline = read_file('/proc/cmdline')
    if m := CMDLINE_CONSOLE_RE.search(kernel_cmdline):
        device = m.group("device") # "ttyS0"
        speed = m.group("speed")   # Baud rate/speed, e.g. "115200"

    return (device, speed)

def activate(config: ConfigTree):
    # Configure the kernel serial console only once during live boot.
    # During installation, the user can define the console. If this is not
    # limited to live boot, the serial interface will always be re-added during
    # system boot, even if it was removed from config.boot.
    if not is_live_boot():
        return

    (device, speed) = get_kernel_serial_console()
    if device and speed:
        # The kernel was booted with a configured serial console, but no
        # console is configured in the CLI; align/fix the CLI configuration.
        if not config.exists(base + [device]):
            config.set(base + [device, 'speed'], value=speed)
            config.set_tag(base)
