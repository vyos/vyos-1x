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
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

from pathlib import Path
from re import compile, MULTILINE, DOTALL
from functools import wraps
from copy import deepcopy
from typing import Union

from vyos.system import disk, grub, image, SYSTEM_CFG_VER
from vyos.template import render

TMPL_GRUB_COMPAT: str = 'grub/grub_compat.j2'

# define regexes and variables
REGEX_VERSION = r'^menuentry "[^\n]*{\n[^}]*\s+linux /boot/(?P<version>\S+)/[^}]*}'
REGEX_MENUENTRY = r'^menuentry "[^\n]*{\n[^}]*\s+linux /boot/(?P<version>\S+)/vmlinuz (?P<options>[^\n]+)\n[^}]*}'
REGEX_CONSOLE = r'^.*console=(?P<console_type>[^\s\d]+)(?P<console_num>[\d]+)(,(?P<console_speed>[\d]+))?.*$'
REGEX_SANIT_CONSOLE = r'\ ?console=[^\s\d]+[\d]+(,\d+)?\ ?'
REGEX_SANIT_INIT = r'\ ?init=\S*\ ?'
REGEX_SANIT_QUIET = r'\ ?quiet\ ?'
PW_RESET_OPTION = 'init=/opt/vyatta/sbin/standalone_root_pw_reset'


class DowngradingImageTools(Exception):
    """Raised when attempting to add an image with an earlier version
    of image-tools than the current system, as indicated by the value
    of SYSTEM_CFG_VER or absence thereof."""
    pass


def mode():
    if grub.get_cfg_ver() >= SYSTEM_CFG_VER:
        return False

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


def get_search_root(unparsed: str) -> str:
    unparsed_lines = unparsed.splitlines()
    search_root = next((x for x in unparsed_lines if 'search' in x), '')
    return search_root


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
    # legacy tools add 'quiet' on add system image; this is not desired
    regex_filter = compile(REGEX_SANIT_QUIET)
    boot_opts = regex_filter.sub(' ', boot_opts)

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
    speed = entry_dict.get('console_speed', None)
    entry_dict['console_speed'] = speed if speed is not None else '115200'
    entry_dict['boot_opts'] = sanitize_boot_opts(entry[1])

    return entry_dict


def parse_menuentries(grub_path: str) -> list:
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


def prune_vyos_versions(root_dir: str = '') -> None:
    """Delete vyos-versions files of registered images subsequently deleted
    or renamed by legacy image-tools

    Args:
        root_dir (str): an optional path to the root directory
    """
    if not root_dir:
        root_dir = disk.find_persistence()

    version_files = Path(f'{root_dir}/{grub.GRUB_DIR_VYOS_VERS}').glob('*.cfg')

    for file in version_files:
        version = Path(file).stem
        if not Path(f'{root_dir}/boot/{version}').is_dir():
            grub.version_del(version, root_dir)


def update_cfg_ver(root_dir:str = '') -> int:
    """Get minumum version of image-tools across all installed images

    Args:
        root_dir (str): an optional path to the root directory

    Returns:
        int: minimum version of image-tools
    """
    if not root_dir:
        root_dir = disk.find_persistence()

    prune_vyos_versions(root_dir)

    images_details = image.get_images_details()
    cfg_version = min(d['tools_version'] for d in images_details)

    return cfg_version


def get_default(data: dict, root_dir: str = '') -> Union[int, None]:
    """Translate default version to menuentry index

    Args:
        data (dict): boot data
        root_dir (str): an optional path to the root directory

    Returns:
        int: index of default version in menu_entries or None
    """
    if not root_dir:
        root_dir = disk.find_persistence()

    grub_cfg_main = f'{root_dir}/{grub.GRUB_CFG_MAIN}'

    menu_entries = data.get('versions', [])
    console_type = data.get('console_type', 'tty')
    console_num = data.get('console_num', '0')
    image_name = image.get_default_image()

    sublist = list(filter(lambda x: (x.get('version') == image_name and
                                     x.get('console_type') == console_type and
                                     x.get('bootmode') == 'normal'),
                          menu_entries))

    if sublist:
        return menu_entries.index(sublist[0])

    return None


def update_version_list(root_dir: str = '') -> list[dict]:
    """Update list of dicts of installed version boot data

    Args:
        root_dir (str): an optional path to the root directory

    Returns:
        list: list of dicts of installed version boot data
    """
    if not root_dir:
        root_dir = disk.find_persistence()

    grub_cfg_main = f'{root_dir}/{grub.GRUB_CFG_MAIN}'

    # get list of versions in menuentries
    menu_entries = parse_menuentries(grub_cfg_main)
    menu_versions = find_versions(menu_entries)

    # remove deprecated console-type ttyUSB
    menu_entries = list(filter(lambda x: x.get('console_type') != 'ttyUSB',
                               menu_entries))

    # get list of versions added/removed by image-tools
    current_versions = grub.version_list(root_dir)

    remove = list(set(menu_versions) - set(current_versions))
    for ver in remove:
        menu_entries = list(filter(lambda x: x.get('version') != ver,
                                   menu_entries))

    # reset boot_opts in case of config update
    for entry in menu_entries:
        entry['boot_opts'] = grub.get_boot_opts(entry['version'])

    add = list(set(current_versions) - set(menu_versions))
    for ver in add:
        last = menu_entries[0].get('version')
        new = deepcopy(list(filter(lambda x: x.get('version') == last,
                                   menu_entries)))
        for e in new:
            boot_opts = grub.get_boot_opts(ver)
            e.update({'version': ver, 'boot_opts': boot_opts})

        menu_entries = new + menu_entries

    return menu_entries


def grub_cfg_fields(root_dir: str = '') -> dict:
    """Gather fields for rendering grub.cfg

    Args:
        root_dir (str): an optional path to the root directory

    Returns:
        dict: dictionary for rendering TMPL_GRUB_COMPAT
    """
    if not root_dir:
        root_dir = disk.find_persistence()

    grub_cfg_main = f'{root_dir}/{grub.GRUB_CFG_MAIN}'
    grub_vars = f'{root_dir}/{grub.CFG_VYOS_VARS}'

    fields = grub.vars_read(grub_vars)
    # 'default' and 'timeout' from legacy grub.cfg resets 'default' to
    # index, rather than uuid
    fields |= grub.vars_read(grub_cfg_main)

    fields['tools_version'] = SYSTEM_CFG_VER
    menu_entries = update_version_list(root_dir)
    fields['versions'] = menu_entries

    default = get_default(fields, root_dir)
    if default is not None:
        fields['default'] = default

    modules = grub.modules_read(grub_cfg_main)
    fields['modules'] = modules

    unparsed = filter_unparsed(grub_cfg_main).splitlines()
    search_root = next((x for x in unparsed if 'search' in x), '')
    fields['search_root'] = search_root

    return fields


def render_grub_cfg(root_dir: str = '') -> None:
    """Render grub.cfg for legacy compatibility"""
    if not root_dir:
        root_dir = disk.find_persistence()

    grub_cfg_main = f'{root_dir}/{grub.GRUB_CFG_MAIN}'

    fields = grub_cfg_fields(root_dir)
    render(grub_cfg_main, TMPL_GRUB_COMPAT, fields)


def grub_cfg_update(func):
    """Decorator to update grub.cfg after function call"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        ret = func(*args, **kwargs)
        if mode():
            render_grub_cfg()
        return ret
    return wrapper
