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

import platform

from pathlib import Path
from re import MULTILINE, compile as re_compile
from shutil import copy2
from uuid import uuid5, NAMESPACE_URL, UUID

from vyos.template import render
from vyos.utils.process import cmd, rc_cmd
from vyos.system import disk

# Define variables
GRUB_DIR_MAIN: str = '/boot/grub'
GRUB_CFG_MAIN: str = f'{GRUB_DIR_MAIN}/grub.cfg'
GRUB_DIR_VYOS: str = f'{GRUB_DIR_MAIN}/grub.cfg.d'
CFG_VYOS_HEADER: str = f'{GRUB_DIR_VYOS}/00-vyos-header.cfg'
CFG_VYOS_MODULES: str = f'{GRUB_DIR_VYOS}/10-vyos-modules-autoload.cfg'
CFG_VYOS_VARS: str = f'{GRUB_DIR_VYOS}/20-vyos-defaults-autoload.cfg'
CFG_VYOS_COMMON: str = f'{GRUB_DIR_VYOS}/25-vyos-common-autoload.cfg'
CFG_VYOS_PLATFORM: str = f'{GRUB_DIR_VYOS}/30-vyos-platform-autoload.cfg'
CFG_VYOS_MENU: str = f'{GRUB_DIR_VYOS}/40-vyos-menu-autoload.cfg'
CFG_VYOS_OPTIONS: str = f'{GRUB_DIR_VYOS}/50-vyos-options.cfg'
GRUB_DIR_VYOS_VERS: str = f'{GRUB_DIR_VYOS}/vyos-versions'

TMPL_VYOS_VERSION: str = 'grub/grub_vyos_version.j2'
TMPL_GRUB_VARS: str = 'grub/grub_vars.j2'
TMPL_GRUB_MAIN: str = 'grub/grub_main.j2'
TMPL_GRUB_MENU: str = 'grub/grub_menu.j2'
TMPL_GRUB_MODULES: str = 'grub/grub_modules.j2'
TMPL_GRUB_OPTS: str = 'grub/grub_options.j2'
TMPL_GRUB_COMMON: str = 'grub/grub_common.j2'

# default boot options
BOOT_OPTS_STEM: str = 'boot=live rootdelay=5 noautologin net.ifnames=0 biosdevname=0 vyos-union=/boot/'

# prepare regexes
REGEX_GRUB_VARS: str = r'^set (?P<variable_name>\w+)=[\'"]?(?P<variable_value>.*)(?<![\'"])[\'"]?$'
REGEX_GRUB_MODULES: str = r'^insmod (?P<module_name>.+)$'
REGEX_KERNEL_CMDLINE: str = r'^BOOT_IMAGE=/(?P<boot_type>boot|live)/((?P<image_version>.+)/)?vmlinuz.*$'
REGEX_GRUB_BOOT_OPTS: str = r'^\s*set boot_opts="(?P<boot_opts>[^$]+)"$'


def install(drive_path: str, boot_dir: str, efi_dir: str, id: str = 'VyOS', chroot : str = "") -> None:
    """Install GRUB for both BIOS and EFI modes (hybrid boot)

    Args:
        drive_path (str): path to a drive where GRUB must be installed
        boot_dir (str): a path to '/boot' directory
        efi_dir (str): a path to '/boot/efi' directory
    """

    if chroot:
        chroot_cmd = f"chroot {chroot}"
    else:
        chroot_cmd = ""

    efi_installation_arch = "x86_64"
    if platform.machine() == "aarch64":
        efi_installation_arch = "arm64"
    elif platform.machine() == "x86_64":
        cmd(
            f'{chroot_cmd} grub-install --no-floppy --target=i386-pc \
            --boot-directory={boot_dir}  {drive_path} --force'
        )

    cmd(
        f'{chroot_cmd} grub-install --no-floppy --recheck --target={efi_installation_arch}-efi \
            --force-extra-removable --boot-directory={boot_dir} \
            --efi-directory={efi_dir} --bootloader-id="{id}" \
            --no-uefi-secure-boot'
    )


def gen_version_uuid(version_name: str) -> str:
    """Generate unique ID from version name

    Use UUID5 / NAMESPACE_URL with prefix `uuid5-`

    Args:
        version_name (str): version name

    Returns:
        str: generated unique ID
    """
    ver_uuid: UUID = uuid5(NAMESPACE_URL, version_name)
    ver_id: str = f'uuid5-{ver_uuid}'
    return ver_id


def version_add(version_name: str,
                root_dir: str = '',
                boot_opts: str = '',
                boot_opts_config = None) -> None:
    """Add a new VyOS version to GRUB loader configuration

    Args:
        vyos_version (str): VyOS version name
        root_dir (str): an optional path to the root directory.
        Defaults to empty.
        boot_opts (str): an optional boot options for Linux kernel.
        Defaults to empty.
    """
    if not root_dir:
        root_dir = disk.find_persistence()
    version_config: str = f'{root_dir}/{GRUB_DIR_VYOS_VERS}/{version_name}.cfg'
    render(
        version_config, TMPL_VYOS_VERSION, {
            'version_name': version_name,
            'version_uuid': gen_version_uuid(version_name),
            'boot_opts_default': BOOT_OPTS_STEM + version_name,
            'boot_opts': boot_opts,
            'boot_opts_config': boot_opts_config
        })


def version_del(vyos_version: str, root_dir: str = '') -> None:
    """Delete a VyOS version from GRUB loader configuration

    Args:
        vyos_version (str): VyOS version name
        root_dir (str): an optional path to the root directory.
        Defaults to empty.
    """
    if not root_dir:
        root_dir = disk.find_persistence()
    version_config: str = f'{root_dir}/{GRUB_DIR_VYOS_VERS}/{vyos_version}.cfg'
    Path(version_config).unlink(missing_ok=True)


def version_list(root_dir: str = '') -> list[str]:
    """Generate a list with installed VyOS versions

    Args:
        root_dir (str): an optional path to the root directory.
        Defaults to empty.

    Returns:
        list: A list with versions names

    N.B. coreutils stat reports st_birthtime, but not available in
    Path.stat()/os.stat()
    """
    if not root_dir:
        root_dir = disk.find_persistence()
    versions_files = Path(f'{root_dir}/{GRUB_DIR_VYOS_VERS}').glob('*.cfg')
    versions_order: dict[str, int] = {}
    for file in versions_files:
        p = Path(root_dir).joinpath('boot').joinpath(file.stem)
        command = f'stat -c %W {p.as_posix()}'
        rc, out = rc_cmd(command)
        if rc == 0:
            versions_order[file.stem] = int(out)
    versions_order = sorted(versions_order, key=versions_order.get, reverse=True)
    versions_list: list[str] = list(versions_order)

    return versions_list


def read_env(env_file: str = '') -> dict[str, str]:
    """Read GRUB environment

    Args:
        env_file (str, optional): a path to grub environment file.
        Defaults to empty.

    Returns:
        dict: dictionary with GRUB environment
    """
    if not env_file:
        root_dir: str = disk.find_persistence()
        env_file = f'{root_dir}/{GRUB_DIR_MAIN}/grubenv'

    env_content: str = cmd(f'grub-editenv {env_file} list').splitlines()
    regex_filter = re_compile(r'^(?P<variable_name>.*)=(?P<variable_value>.*)$')
    env_dict: dict[str, str] = {}
    for env_item in env_content:
        search_result = regex_filter.fullmatch(env_item)
        if search_result:
            search_result_dict: dict[str, str] = search_result.groupdict()
            variable_name: str = search_result_dict.get('variable_name', '')
            variable_value: str = search_result_dict.get('variable_value', '')
            if variable_name and variable_value:
                env_dict.update({variable_name: variable_value})
    return env_dict


def get_cfg_ver(root_dir: str = '') -> int:
    """Get current version of GRUB configuration

    Args:
        root_dir (str, optional): an optional path to the root directory.
        Defaults to empty.

    Returns:
        int: a configuration version
    """
    if not root_dir:
        root_dir = disk.find_persistence()

    cfg_ver: str = vars_read(f'{root_dir}/{CFG_VYOS_HEADER}').get(
            'VYOS_CFG_VER')
    if cfg_ver:
        cfg_ver_int: int = int(cfg_ver)
    else:
        cfg_ver_int: int = 0
    return cfg_ver_int


def write_cfg_ver(cfg_ver: int, root_dir: str = '') -> None:
    """Write version number of GRUB configuration

    Args:
        cfg_ver (int): a version number to write
        root_dir (str, optional): an optional path to the root directory.
        Defaults to empty.

    Returns:
        int: a configuration version
    """
    if not root_dir:
        root_dir = disk.find_persistence()

    vars_file: str = f'{root_dir}/{CFG_VYOS_HEADER}'
    vars_current: dict[str, str] = vars_read(vars_file)
    vars_current['VYOS_CFG_VER'] = str(cfg_ver)
    vars_write(vars_file, vars_current)


def vars_read(grub_cfg: str) -> dict[str, str]:
    """Read variables from a GRUB configuration file

    Args:
        grub_cfg (str): a path to the GRUB config file

    Returns:
        dict: a dictionary with variables and values
    """
    vars_dict: dict[str, str] = {}
    regex_filter = re_compile(REGEX_GRUB_VARS)
    try:
        config_text: list[str] = Path(grub_cfg).read_text().splitlines()
    except FileNotFoundError:
        return vars_dict
    for line in config_text:
        search_result = regex_filter.fullmatch(line)
        if search_result:
            search_dict = search_result.groupdict()
            variable_name: str = search_dict.get('variable_name', '')
            variable_value: str = search_dict.get('variable_value', '')
            if variable_name and variable_value:
                vars_dict.update({variable_name: variable_value})
    return vars_dict


def modules_read(grub_cfg: str) -> list[str]:
    """Read modules list from a GRUB configuration file

    Args:
        grub_cfg (str): a path to the GRUB config file

    Returns:
        list: a list with modules to load
    """
    mods_list: list[str] = []
    regex_filter = re_compile(REGEX_GRUB_MODULES, MULTILINE)
    try:
        config_text = Path(grub_cfg).read_text()
    except FileNotFoundError:
        return mods_list
    mods_list = regex_filter.findall(config_text)

    return mods_list


def modules_write(grub_cfg: str, mods_list: list[str]) -> None:
    """Write modules list to a GRUB configuration file (overwrite everything)

    Args:
        grub_cfg (str): a path to GRUB configuration file
        mods_list (list): a list with modules to load
    """
    render(grub_cfg, TMPL_GRUB_MODULES, {'mods_list': mods_list})


def vars_write(grub_cfg: str, grub_vars: dict[str, str]) -> None:
    """Write variables to a GRUB configuration file (overwrite everything)

    Args:
        grub_cfg (str): a path to GRUB configuration file
        grub_vars (dict): a dictionary with new variables
    """
    render(grub_cfg, TMPL_GRUB_VARS, {'vars': grub_vars})

def get_boot_opts(version_name: str, root_dir: str = '') -> str:
    """Read boot_opts setting from version file; return default setting on
    any failure.

    Args:
        version_name (str): version name
        root_dir (str, optional): an optional path to the root directory.
        Defaults to empty.
    """
    if not root_dir:
        root_dir = disk.find_persistence()

    boot_opts_default: str = BOOT_OPTS_STEM + version_name
    boot_opts: str = ''
    regex_filter = re_compile(REGEX_GRUB_BOOT_OPTS)
    version_config: str = f'{root_dir}/{GRUB_DIR_VYOS_VERS}/{version_name}.cfg'
    try:
        config_text: list[str] = Path(version_config).read_text().splitlines()
    except FileNotFoundError:
        return boot_opts_default
    for line in config_text:
        search_result = regex_filter.fullmatch(line)
        if search_result:
            search_dict = search_result.groupdict()
            boot_opts = search_dict.get('boot_opts', '')
            break

    if not boot_opts:
        boot_opts = boot_opts_default

    return boot_opts

def set_default(version_name: str, root_dir: str = '') -> None:
    """Set version as default boot entry

    Args:
        version_name (str): version name
        root_dir (str, optional): an optional path to the root directory.
        Defaults to empty.
    """
    if not root_dir:
        root_dir = disk.find_persistence()

    vars_file = f'{root_dir}/{CFG_VYOS_VARS}'
    vars_current = vars_read(vars_file)
    vars_current['default'] = gen_version_uuid(version_name)
    vars_write(vars_file, vars_current)


def common_write(root_dir: str = '', grub_common: dict[str, str] = {}) -> None:
    """Write common GRUB configuration file (overwrite everything)

    Args:
        root_dir (str, optional): an optional path to the root directory.
        Defaults to empty.
    """
    if not root_dir:
        root_dir = disk.find_persistence()
    common_config = f'{root_dir}/{CFG_VYOS_COMMON}'
    render(common_config, TMPL_GRUB_COMMON, grub_common)


def create_structure(root_dir: str = '') -> None:
    """Create GRUB directories structure

    Args:
        root_dir (str, optional): an optional path to the root directory.
        Defaults to ''.
    """
    if not root_dir:
        root_dir = disk.find_persistence()

    Path(f'{root_dir}/{GRUB_DIR_VYOS_VERS}').mkdir(parents=True, exist_ok=True)


def set_console_type(console_type: str, root_dir: str = '') -> None:
    """Write default console type to GRUB configuration

    Args:
        console_type (str): a default console type
        root_dir (str, optional): an optional path to the root directory.
        Defaults to empty.
    """
    if not root_dir:
        root_dir = disk.find_persistence()

    vars_file: str = f'{root_dir}/{CFG_VYOS_VARS}'
    vars_current: dict[str, str] = vars_read(vars_file)
    vars_current['console_type'] = str(console_type)
    vars_write(vars_file, vars_current)

def set_console_speed(console_speed: str, root_dir: str = '') -> None:
    """Write default console speed to GRUB configuration

    Args:
        console_speed (str): default console speed
        root_dir (str, optional): an optional path to the root directory.
        Defaults to empty.
    """
    if not root_dir:
        root_dir = disk.find_persistence()

    vars_file: str = f'{root_dir}/{CFG_VYOS_VARS}'
    vars_current: dict[str, str] = vars_read(vars_file)
    vars_current['console_speed'] = str(console_speed)
    vars_write(vars_file, vars_current)

def set_kernel_cmdline_options(cmdline_options: str, version_name: str,
                               root_dir: str = '') -> None:
    """Write additional cmdline options to GRUB configuration

    Args:
        cmdline_options (str): cmdline options to add to default boot line
        version_name (str): image version name
        root_dir (str, optional): an optional path to the root directory.
    """
    if not root_dir:
        root_dir = disk.find_persistence()

    version_add(version_name=version_name, root_dir=root_dir,
                boot_opts_config=cmdline_options)


def sort_inodes(dir_path: str) -> None:
    """Sort inodes for files inside a folder
    Regenerate inodes for each file to get the same order for both inodes
    and file names

    GRUB iterates files by inodes, not alphabetically. Therefore, if we
    want to read them in proper order, we need to sort inodes for all
    config files in a folder.

    Args:
        dir_path (str): a path to directory
    """
    dir_content: list[Path] = sorted(Path(dir_path).iterdir())
    temp_list_old: list[Path] = []
    temp_list_new: list[Path] = []

    # create a copy of all files, to get new inodes
    for item in dir_content:
        # skip directories
        if item.is_dir():
            continue
        # create a new copy of file with a temporary name
        copy_path = Path(f'{item.as_posix()}_tmp')
        copy2(item, Path(copy_path))
        temp_list_old.append(item)
        temp_list_new.append(copy_path)

    # delete old files and rename new ones
    for item in temp_list_old:
        item.unlink()
    for item in temp_list_new:
        new_name = Path(f'{item.as_posix()[0:-4]}')
        item.rename(new_name)
