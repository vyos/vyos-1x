# Copyright 2023 VyOS maintainers and contributors <maintainers@vyos.io>
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
from subprocess import run

def sysctl_read(name: str) -> str:
    """Read and return current value of sysctl() option

    Args:
        name (str): sysctl key name

    Returns:
        str: sysctl key value
    """
    tmp = run(['sysctl', '-nb', name], capture_output=True)
    return tmp.stdout.decode()

def sysctl_write(name: str, value: str | int) -> bool:
    """Change value via sysctl()

    Args:
        name (str): sysctl key name
        value (str | int): sysctl key value

    Returns:
        bool: True if changed, False otherwise
    """
    # convert other types to string before comparison
    if not isinstance(value, str):
        value = str(value)
    # do not change anything if a value is already configured
    if sysctl_read(name) == value:
        return True
    # return False if sysctl call failed
    if run(['sysctl', '-wq', f'{name}={value}']).returncode != 0:
        return False
    # compare old and new values
    # sysctl may apply value, but its actual value will be
    # different from requested
    if sysctl_read(name) == value:
        return True
    # False in other cases
    return False

def sysctl_apply(sysctl_dict: dict[str, str], revert: bool = True) -> bool:
    """Apply sysctl values.

    Args:
        sysctl_dict (dict[str, str]): dictionary with sysctl keys with values
        revert (bool, optional): Revert to original values if new were not
        applied. Defaults to True.

    Returns:
        bool: True if all params configured properly, False in other cases
    """
    # get current values
    sysctl_original: dict[str, str] = {}
    for key_name in sysctl_dict.keys():
        sysctl_original[key_name] = sysctl_read(key_name)
    # apply new values and revert in case one of them was not applied
    for key_name, value in sysctl_dict.items():
        if not sysctl_write(key_name, value):
            if revert:
                sysctl_apply(sysctl_original, revert=False)
            return False
    # everything applied
    return True

def find_device_file(device):
    """ Recurively search /dev for the given device file and return its full path.
        If no device file was found 'None' is returned """
    from fnmatch import fnmatch

    for root, dirs, files in os.walk('/dev'):
        for basename in files:
            if fnmatch(basename, device):
                return os.path.join(root, basename)

    return None

def load_as_module(name: str, path: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
