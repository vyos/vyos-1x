# Copyright 2023-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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
