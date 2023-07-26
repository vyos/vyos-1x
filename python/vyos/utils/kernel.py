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

def check_kmod(k_mod):
    """ Common utility function to load required kernel modules on demand """
    from vyos import ConfigError
    from vyos.utils.process import call
    if isinstance(k_mod, str):
        k_mod = k_mod.split()
    for module in k_mod:
        if not os.path.exists(f'/sys/module/{module}'):
            if call(f'modprobe {module}') != 0:
                raise ConfigError(f'Loading Kernel module {module} failed')

def unload_kmod(k_mod):
    """ Common utility function to unload required kernel modules on demand """
    from vyos import ConfigError
    from vyos.utils.process import call
    if isinstance(k_mod, str):
        k_mod = k_mod.split()
    for module in k_mod:
        if os.path.exists(f'/sys/module/{module}'):
            if call(f'rmmod {module}') != 0:
                raise ConfigError(f'Unloading Kernel module {module} failed')
