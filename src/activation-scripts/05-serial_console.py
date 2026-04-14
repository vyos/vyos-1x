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

from vyos.configtree import ConfigTree
from vyos.system.image import is_live_boot
from vyos.utils.kernel import get_kernel_serial_console
from vyos.utils.serial import is_tty

base = ['system', 'console', 'device']

def activate(config: ConfigTree):
    # Configure the kernel serial console only once during live boot. During
    # installation, the user can define the console type (VT TTY or serial
    # TTY). If this is not limited to live boot, the serial interface will
    # always be re-added during system boot, even if it was removed from
    # config.boot.
    if not is_live_boot():
        return

    # Parse current kernel cmdline and continue only for valid serial console
    # data. Prevent writing incomplete/invalid console settings to config.boot.
    console_type, console_num, console_speed = get_kernel_serial_console()
    device = f'{console_type}{console_num}'
    if not is_tty(device) or not console_speed:
        return

    # The kernel was booted with a configured serial console, but no console
    # is configured via CLI; align/fix the CLI configuration.
    if not config.exists(base + [device]):
        config.set(base + [device, 'speed'], value=console_speed)
        config.set_tag(base)
