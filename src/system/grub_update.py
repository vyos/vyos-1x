#!/usr/bin/env python3
#
# Copyright 2022 VyOS maintainers and contributors <maintainers@vyos.io>
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
from re import compile, MULTILINE, DOTALL
from sys import exit

from vyos.system import disk, grub, image
from vyos.template import render

# define configuration version
CFG_VER = 1

# define regexes and variables
REGEX_VERSION = r'^menuentry "[^\n]*{\n[^}]*\s+linux /boot/(?P<version>\S+)/[^}]*}'
REGEX_MENUENTRY = r'^menuentry "[^\n]*{\n[^}]*\s+linux /boot/(?P<version>\S+)/vmlinuz (?P<options>[^\n]+)\n[^}]*}'
REGEX_CONSOLE = r'^.*console=(?P<console_type>[^\s\d]+)(?P<console_num>[\d]+).*$'
REGEX_SANIT_CONSOLE = r'\ ?console=[^\s\d]+[\d]+(,\d+)?\ ?'
REGEX_SANIT_INIT = r'\ ?init=\S*\ ?'
PW_RESET_OPTION = 'init=/opt/vyatta/sbin/standalone_root_pw_reset'


def cfg_check_update() -> bool:
    """Check if GRUB structure update is required

    Returns:
        bool: False if not required, True if required
    """
    current_ver = grub.get_cfg_ver()
    if current_ver and current_ver >= CFG_VER:
        return False
    else:
        return True


def find_versions(menu_entries: list) -> list:
    """Find unique VyOS versions from menu entries

    Args:
        menu_entries (list): a list with menu entries

    Returns:
        list: List of installed versions
    """
    versions = []
    for vyos_ver in menu_entries:
        versions.append(vyos_ver.get('version'))
    # remove duplicates
    versions = list(set(versions))
    return versions


def filter_unparsed(grub_path: str) -> str:
    """Find currently installed VyOS version

    Args:
        grub_path (str): a path to the grub.cfg file

    Returns:
        str: unparsed grub.cfg items
    """
    config_text = Path(grub_path).read_text()
    regex_filter = compile(REGEX_VERSION, MULTILINE | DOTALL)
    filtered = regex_filter.sub('', config_text)
    regex_filter = compile(grub.REGEX_GRUB_VARS, MULTILINE)
    filtered = regex_filter.sub('', filtered)
    regex_filter = compile(grub.REGEX_GRUB_MODULES, MULTILINE)
    filtered = regex_filter.sub('', filtered)
    # strip extra new lines
    filtered = filtered.strip()
    return filtered


def sanitize_boot_opts(boot_opts: str) -> str:
    """Sanitize boot options from console and init

    Args:
        boot_opts (str): boot options

    Returns:
        str: sanitized boot options
    """
    regex_filter = compile(REGEX_SANIT_CONSOLE)
    boot_opts = regex_filter.sub('', boot_opts)
    regex_filter = compile(REGEX_SANIT_INIT)
    boot_opts = regex_filter.sub('', boot_opts)

    return boot_opts


def parse_entry(entry: tuple) -> dict:
    """Parse GRUB menuentry

    Args:
        entry (tuple): tuple of (version, options)

    Returns:
        dict: dictionary with parsed options
    """
    # save version to dict
    entry_dict = {'version': entry[0]}
    # detect boot mode type
    if PW_RESET_OPTION in entry[1]:
        entry_dict['bootmode'] = 'pw_reset'
    else:
        entry_dict['bootmode'] = 'normal'
    # find console type and number
    regex_filter = compile(REGEX_CONSOLE)
    entry_dict.update(regex_filter.match(entry[1]).groupdict())
    entry_dict['boot_opts'] = sanitize_boot_opts(entry[1])

    return entry_dict


def parse_menuntries(grub_path: str) -> list:
    """Parse all GRUB menuentries

    Args:
        grub_path (str): a path to GRUB config file

    Returns:
        list: list with menu items (each item is a dict)
    """
    menuentries = []
    # read configuration file
    config_text = Path(grub_path).read_text()
    # parse menuentries to tuples (version, options)
    regex_filter = compile(REGEX_MENUENTRY, MULTILINE)
    filter_results = regex_filter.findall(config_text)
    # parse each entry
    for entry in filter_results:
        menuentries.append(parse_entry(entry))

    return menuentries


if __name__ == '__main__':
    if image.is_live_boot():
        exit(0)

    # Skip everything if update is not required
    if not cfg_check_update():
        exit(0)

    # find root directory of persistent storage
    root_dir = disk.find_persistence()

    # read current GRUB config
    grub_cfg_main = f'{root_dir}/{image.GRUB_DIR_MAIN}/grub.cfg'
    vars = grub.vars_read(grub_cfg_main)
    modules = grub.modules_read(grub_cfg_main)
    vyos_menuentries = parse_menuntries(grub_cfg_main)
    vyos_versions = find_versions(vyos_menuentries)
    unparsed_items = filter_unparsed(grub_cfg_main)

    # find default values
    default_entry = vyos_menuentries[int(vars['default'])]
    default_settings = {
        'default': grub.gen_version_uuid(default_entry['version']),
        'bootmode': default_entry['bootmode'],
        'console_type': default_entry['console_type'],
        'console_num': default_entry['console_num']
    }
    vars.update(default_settings)

    # print(f'vars: {vars}')
    # print(f'modules: {modules}')
    # print(f'vyos_menuentries: {vyos_menuentries}')
    # print(f'unparsed_items: {unparsed_items}')

    # create new files
    grub_cfg_vars = f'{root_dir}/{image.CFG_VYOS_VARS}'
    grub_cfg_modules = f'{root_dir}/{grub.CFG_VYOS_MODULES}'
    grub_cfg_platform = f'{root_dir}/{grub.CFG_VYOS_PLATFORM}'
    grub_cfg_menu = f'{root_dir}/{grub.CFG_VYOS_MENU}'
    grub_cfg_options = f'{root_dir}/{grub.CFG_VYOS_OPTIONS}'

    render(grub_cfg_main, grub.TMPL_GRUB_MAIN, {})
    Path(image.GRUB_DIR_VYOS).mkdir(exist_ok=True)
    grub.vars_write(grub_cfg_vars, vars)
    grub.modules_write(grub_cfg_modules, modules)
    # Path(grub_cfg_platform).write_text(unparsed_items)
    grub.common_write()
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
    grub.write_cfg_ver(CFG_VER, root_dir)
    exit(0)
