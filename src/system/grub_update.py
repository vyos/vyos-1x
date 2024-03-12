#!/usr/bin/env python3
#
# Copyright 2023 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This file is part of VyOS.
#
# VyOS is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# VyOS is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# VyOS. If not, see <https://www.gnu.org/licenses/>.

from pathlib import Path
from sys import exit

from vyos.system import disk, grub, image, compat, SYSTEM_CFG_VER
from vyos.template import render


def cfg_check_update() -> bool:
    """Check if GRUB structure update is required

    Returns:
        bool: False if not required, True if required
    """
    current_ver = grub.get_cfg_ver()
    if current_ver and current_ver >= SYSTEM_CFG_VER:
        return False

    return True


if __name__ == '__main__':
    if image.is_live_boot():
        exit(0)

    if image.is_running_as_container():
        exit(0)

    # Skip everything if update is not required
    if not cfg_check_update():
        exit(0)

    # find root directory of persistent storage
    root_dir = disk.find_persistence()

    # read current GRUB config
    grub_cfg_main = f'{root_dir}/{grub.GRUB_CFG_MAIN}'
    vars = grub.vars_read(grub_cfg_main)
    modules = grub.modules_read(grub_cfg_main)
    vyos_menuentries = compat.parse_menuentries(grub_cfg_main)
    vyos_versions = compat.find_versions(vyos_menuentries)
    unparsed_items = compat.filter_unparsed(grub_cfg_main)
    # compatibilty for raid installs
    search_root = compat.get_search_root(unparsed_items)
    common_dict = {}
    common_dict['search_root'] = search_root
    # find default values
    default_entry = vyos_menuentries[int(vars['default'])]
    default_settings = {
        'default': grub.gen_version_uuid(default_entry['version']),
        'bootmode': default_entry['bootmode'],
        'console_type': default_entry['console_type'],
        'console_num': default_entry['console_num'],
        'console_speed': default_entry['console_speed']
    }
    vars.update(default_settings)

    # create new files
    grub_cfg_vars = f'{root_dir}/{grub.CFG_VYOS_VARS}'
    grub_cfg_modules = f'{root_dir}/{grub.CFG_VYOS_MODULES}'
    grub_cfg_platform = f'{root_dir}/{grub.CFG_VYOS_PLATFORM}'
    grub_cfg_menu = f'{root_dir}/{grub.CFG_VYOS_MENU}'
    grub_cfg_options = f'{root_dir}/{grub.CFG_VYOS_OPTIONS}'

    Path(image.GRUB_DIR_VYOS).mkdir(exist_ok=True)
    grub.vars_write(grub_cfg_vars, vars)
    grub.modules_write(grub_cfg_modules, modules)
    grub.common_write(grub_common=common_dict)
    render(grub_cfg_menu, grub.TMPL_GRUB_MENU, {})
    render(grub_cfg_options, grub.TMPL_GRUB_OPTS, {})

    # create menu entries
    for vyos_ver in vyos_versions:
        boot_opts = None
        for entry in vyos_menuentries:
            if entry.get('version') == vyos_ver and entry.get(
                    'bootmode') == 'normal':
                boot_opts = entry.get('boot_opts')
        grub.version_add(vyos_ver, root_dir, boot_opts)

    # update structure version
    cfg_ver = compat.update_cfg_ver(root_dir)
    grub.write_cfg_ver(cfg_ver, root_dir)

    if compat.mode():
        compat.render_grub_cfg(root_dir)
    else:
        render(grub_cfg_main, grub.TMPL_GRUB_MAIN, {})

    # sort inodes (to make GRUB read config files in alphabetical order)
    grub.sort_inodes(f'{root_dir}/{grub.GRUB_DIR_VYOS}')
    grub.sort_inodes(f'{root_dir}/{grub.GRUB_DIR_VYOS_VERS}')

    exit(0)
