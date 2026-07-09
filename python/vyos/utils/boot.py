# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import os

from vyos.utils.file import read_file

CMDLINE_PATH = '/proc/cmdline'


def boot_configuration_complete() -> bool:
    """ Check if the boot config loader has completed
    """
    from vyos.defaults import config_status
    if os.path.isfile(config_status):
        return True
    return False

def boot_configuration_success() -> bool:
    from vyos.defaults import config_status
    try:
        with open(config_status) as f:
            res = f.read().strip()
    except FileNotFoundError:
        return False
    if int(res) == 0:
        return True
    return False

def is_uefi_system() -> bool:
    efi_fw_dir = '/sys/firmware/efi'
    return os.path.exists(efi_fw_dir) and os.path.isdir(efi_fw_dir)


def get_kernel_boot_args(argument=None) -> str | None:
    """Read and parse kernel boot arguments from the kernel command line.

    Args:
        argument: The name of a specific boot argument to look up (e.g.
                  'crashkernel'). If omitted or None, the full raw command
                  line string is returned.

    Returns:
        If argument is None: the full kernel command line string.
        If argument is given: the value of that argument (the part after '='),
        or None if the argument is not present on the command line.

    Examples:
        >>> get_kernel_boot_args()
        'ro quiet crashkernel=256M console=tty0'

        >>> get_kernel_boot_args('crashkernel')
        '256M'

        >>> get_kernel_boot_args('nonexistent')
        None
    """
    cmdline = read_file(CMDLINE_PATH)
    if not argument:
        return cmdline

    # Kernel arguments with values are formatted as 'key=value' tokens
    # separated by spaces. Build the prefix to match against:
    key = f'{argument}='

    for part in cmdline.split():
        if part.startswith(key):
            # Strip the 'key=' prefix and return only the value portion
            return part[len(key) :]

    return None
