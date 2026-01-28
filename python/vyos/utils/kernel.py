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

# A list of used Kernel constants
# https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/net/wireguard/messages.h?h=linux-6.6.y#n45
WIREGUARD_REKEY_AFTER_TIME = 120


def load_module(name: str, quiet: bool = True, dry_run: bool = False) -> int:
    """Load a kernel module via modprobe.

    Returns the modprobe return code.
    """

    from vyos.utils.process import run

    if is_module_loaded(name):
        return 0

    cmd = ['modprobe']
    if dry_run:
        cmd.append('-n')
    if quiet:
        cmd.append('-q')
    cmd.append(name)
    return run(cmd)


def unload_module(name: str) -> int:
    """Unload a kernel module via rmmod.

    Returns the rmmod return code.
    """

    from vyos.utils.process import run

    if not is_module_loaded(name):
        return 0

    return run(['rmmod', name])

def check_kmod(k_mod):
    """ Common utility function to load required kernel modules on demand """
    from vyos import ConfigError
    if isinstance(k_mod, str):
        k_mod = k_mod.split()
    for module in k_mod:
        if load_module(module) != 0:
            raise ConfigError(f'Loading Kernel module {module} failed')


def is_module_loaded(module):
    """Common utility function to check whether module is loaded"""
    return os.path.exists(f'/sys/module/{module}')

def unload_kmod(k_mod):
    """ Common utility function to unload required kernel modules on demand """
    from vyos import ConfigError
    if isinstance(k_mod, str):
        k_mod = k_mod.split()
    for module in k_mod:
        if unload_module(module) != 0:
            raise ConfigError(f'Unloading Kernel module {module} failed')

def list_loaded_modules():
    """ Returns the list of currently loaded kernel modules """
    from os import listdir
    return listdir('/sys/module/')

def get_module_data(module: str):
    """ Retrieves information about a module """
    from os import listdir
    from os.path import isfile, dirname, basename, join
    from vyos.utils.file import read_file

    def _get_file(path):
        # Some files inside some modules are not readable at all,
        # we just skip them.
        try:
            return read_file(path)
        except PermissionError:
            return None

    mod_path = join('/sys/module', module)
    mod_data = {"name": module, "fields": {}, "parameters": {}}

    for f in listdir(mod_path):
        if f in ["sections", "notes", "uevent"]:
            # The uevent file is not readable
            # and module build info and memory layout
            # in notes and sections generally aren't useful
            # for anything but kernel debugging.
            pass
        elif f == "drivers":
            # Drivers are dir symlinks,
            # we just list them
            drivers = listdir(join(mod_path, f))
            if drivers:
                mod_data["drivers"] = drivers
        elif f == "holders":
            # Holders (module that use this one)
            # are always symlink to other modules.
            # We only need the list.
            holders = listdir(join(mod_path, f))
            if holders:
                mod_data["holders"] = holders
        elif f == "parameters":
            # Many modules keep their configuration
            # in the "parameters" subdir.
            ppath = join(mod_path, "parameters")
            ps = listdir(ppath)
            for p in ps:
                data = _get_file(join(ppath, p))
                if data:
                    mod_data["parameters"][p] = data
        else:
            # Everything else...
            # There are standard fields like refcount and initstate,
            # but many modules also keep custom information or settings
            # in top-level fields.
            # For now we don't separate well-known and custom fields.
            if isfile(join(mod_path, f)):
                data = _get_file(join(mod_path, f))
                if data:
                    mod_data["fields"][f] = data
            else:
                raise RuntimeError(f"Unexpected directory inside module {module}: {f}")

    return mod_data

def lsmod():
    """ Returns information about all loaded modules.
        Like lsmod(8), but more detailed.
    """
    mods_data = []
    for m in list_loaded_modules():
        mods_data.append(get_module_data(m))
    return mods_data
