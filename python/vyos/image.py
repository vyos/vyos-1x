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

from json import loads as json_loads
from os import sync
from pathlib import Path
from re import MULTILINE, compile as re_compile
from tempfile import TemporaryDirectory
from typing import TypedDict, Union
from uuid import uuid5, NAMESPACE_URL

from psutil import disk_partitions

from vyos.template import render
from vyos.util import run, cmd
from vyos import version

# Define variables
GRUB_DIR_MAIN: str = '/boot/grub'
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

# prepare regexes
REGEX_GRUB_VARS: str = r'^set (?P<variable_name>.+)=[\'"]?(?P<variable_value>.*)(?<![\'"])[\'"]?$'
REGEX_GRUB_MODULES: str = r'^insmod (?P<module_name>.+)$'
REGEX_KERNEL_CMDLINE: str = r'^BOOT_IMAGE=/(?P<boot_type>boot|live)/((?P<image_version>.+)/)?vmlinuz.*$'


# structures definitions
class ImageDetails(TypedDict):
    name: str
    version: str
    disk_ro: int
    disk_rw: int
    disk_total: int


class BootDetails(TypedDict):
    image_default: str
    image_running: str
    images_available: list[str]
    console_type: str
    console_num: int


class Grub:

    def install(self, drive_path: str, boot_dir: str,
                     efi_dir: str) -> None:
        """Install GRUB for both BIOS and EFI modes (hybrid boot)

        Args:
            drive_path (str): path to a drive where GRUB must be installed
            boot_dir (str): a path to '/boot' directory
            efi_dir (str): a path to '/boot/efi' directory
        """
        commands: list[str] = [
            f'grub-install --no-floppy --target=i386-pc --boot-directory={boot_dir} \
                {drive_path} --force',
            f'grub-install --no-floppy --recheck --target=x86_64-efi \
                --force-extra-removable --boot-directory={boot_dir} \
                --efi-directory={efi_dir} --bootloader-id="VyOS" \
                --no-uefi-secure-boot'
        ]
        for command in commands:
            run(command)

    def gen_version_uuid(self, version_name: str) -> str:
        """Generate unique ID from version name

        Use UUID5 / NAMESPACE_URL with prefix `uuid5-`

        Args:
            version_name (str): version name

        Returns:
            str: generated unique ID
        """
        ver_uuid = uuid5(NAMESPACE_URL, version_name)
        ver_id = f'uuid5-{ver_uuid}'
        return ver_id

    def version_add(self,
                         version_name: str,
                         root_dir: str = '',
                         boot_opts: str = '') -> None:
        """Add a new VyOS version to GRUB loader configuration

        Args:
            vyos_version (str): VyOS version name
            root_dir (str): an optional path to the root directory.
            Defaults to empty.
            boot_opts (str): an optional boot options for Linux kernel.
            Defaults to empty.
        """
        if not root_dir:
            root_dir = find_presistence()
        version_config: str = f'{root_dir}/{GRUB_DIR_VYOS_VERS}/{version_name}.cfg'
        render(
            version_config, TMPL_VYOS_VERSION, {
                'version_name': version_name,
                'version_uuid': self.gen_version_uuid(version_name),
                'boot_opts': boot_opts
            })

    def version_del(self, vyos_version: str, root_dir: str = '') -> None:
        """Delete a VyOS version from GRUB loader configuration

        Args:
            vyos_version (str): VyOS version name
            root_dir (str): an optional path to the root directory.
            Defaults to empty.
        """
        if not root_dir:
            root_dir = find_presistence()
        version_config = f'{root_dir}/{GRUB_DIR_VYOS_VERS}/{vyos_version}.cfg'
        Path(version_config).unlink(missing_ok=True)

    def grub_version_list(self, root_dir: str = '') -> list[str]:
        """Generate a list with installed VyOS versions

        Args:
            root_dir (str): an optional path to the root directory.
            Defaults to empty.

        Returns:
            list: A list with versions names
        """
        if not root_dir:
            root_dir = find_presistence()
        versions_files = Path(f'{root_dir}/{GRUB_DIR_VYOS_VERS}').glob('*.cfg')
        versions_list: list[str] = []
        for file in versions_files:
            versions_list.append(file.stem)
        return versions_list

    def grub_read_env(self, env_file: str = '') -> dict[str, str]:
        """Read GRUB environment

        Args:
            env_file (str, optional): a path to grub environment file.
            Defaults to empty.

        Returns:
            dict: dictionary with GRUB environment
        """
        if not env_file:
            root_dir: str = find_presistence()
            env_file = f'{root_dir}/{GRUB_DIR_MAIN}/grubenv'

        env_content: str = cmd(f'grub-editenv {env_file} list').splitlines()
        regex_filter = re_compile(
            r'^(?P<variable_name>.*)=(?P<variable_value>.*)$')
        env_dict: dict[str, str] = {}
        for env_item in env_content:
            search_result = regex_filter.fullmatch(env_item)
            if search_result:
                search_result_dict: dict[str, str] = search_result.groupdict()
                variable_name: str = search_result_dict.get('variable_name', '')
                variable_value: str = search_result_dict.get(
                    'variable_value', '')
                if variable_name and variable_value:
                    env_dict.update({variable_name: variable_value})
        return env_dict

    def grub_get_cfg_ver(self, root_dir: str = '') -> int:
        """Get current version of GRUB configuration

        Args:
            root_dir (str, optional): an optional path to the root directory.
            Defaults to empty.

        Returns:
            int: a configuration version
        """
        if not root_dir:
            root_dir = find_presistence()

        cfg_ver: Union[str, None] = grub_vars_read(
            f'{root_dir}/{CFG_VYOS_HEADER}').get('VYOS_CFG_VER')
        if cfg_ver:
            cfg_ver_int: int = int(cfg_ver)
        else:
            cfg_ver_int: int = 0
        return cfg_ver_int

    def grub_write_cfg_ver(self, cfg_ver: int, root_dir: str = '') -> None:
        """Write version number of GRUB configuration

        Args:
            cfg_ver (int): a version number to write
            root_dir (str, optional): an optional path to the root directory.
            Defaults to empty.

        Returns:
            int: a configuration version
        """
        if not root_dir:
            root_dir = find_presistence()

        vars_file: str = f'{root_dir}/{CFG_VYOS_HEADER}'
        vars_current: dict[str, str] = grub_vars_read(vars_file)
        vars_current['VYOS_CFG_VER'] = str(cfg_ver)
        grub_vars_write(vars_file, vars_current)

    def grub_vars_read(self, grub_cfg: str) -> dict[str, str]:
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

    def grub_modules_read(self, grub_cfg: str) -> list[str]:
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

    def grub_modules_write(self, grub_cfg: str, mods_list: list[str]) -> None:
        """Write modules list to a GRUB configuration file (overwrite everything)

        Args:
            grub_cfg (str): a path to GRUB configuration file
            mods_list (list): a list with modules to load
        """
        render(grub_cfg, TMPL_GRUB_MODULES, {'mods_list': mods_list})

    def grub_vars_write(self, grub_cfg: str, grub_vars: dict[str, str]) -> None:
        """Write variables to a GRUB configuration file (overwrite everything)

        Args:
            grub_cfg (str): a path to GRUB configuration file
            grub_vars (dict): a dictionary with new variables
        """
        render(grub_cfg, TMPL_GRUB_VARS, {'vars': grub_vars})

    def grub_set_default(self, version_name: str, root_dir: str = '') -> None:
        """Set version as default boot entry

        Args:
            version_name (str): versio name
            root_dir (str, optional): an optional path to the root directory.
            Defaults to empty.
        """
        if not root_dir:
            root_dir = find_presistence()

        vars_file = f'{root_dir}/{CFG_VYOS_VARS}'
        vars_current = grub_vars_read(vars_file)
        vars_current['default'] = self.gen_version_uuid(version_name)
        grub_vars_write(vars_file, vars_current)

    def grub_common_write(self, root_dir: str = '') -> None:
        """Write common GRUB configuration file (overwrite everything)

        Args:
            root_dir (str, optional): an optional path to the root directory.
            Defaults to empty.
        """
        if not root_dir:
            root_dir = find_presistence()
        common_config = f'{root_dir}/{CFG_VYOS_COMMON}'
        render(common_config, TMPL_GRUB_COMMON, {})

    def create_grub_structure(self, root_dir: str = '') -> None:
        """Create GRUB directories structure

        Args:
            root_dir (str, optional): an optional path to the root directory.
            Defaults to ''.
        """
        if not root_dir:
            root_dir = find_presistence()

        Path(f'{root_dir}/GRUB_DIR_VYOS_VERS').mkdir(parents=True,
                                                     exist_ok=True)


def disk_cleanup(drive_path: str) -> None:
    """Clean up disk partition table (MBR and GPT)
    Zeroize primary and secondary headers - first and last 17408 bytes
    (512 bytes * 34 LBA) on a drive

    Args:
        drive_path (str): path to a drive that needs to be cleaned
    """
    # with open(drive_path, 'w+b') as drive:
    #     drive.seek(0)
    #     drive.write(b'0' * 17408)
    #     drive.seek(-17408, 2)
    #     drive.write(b'0' * 17408)
    # # update partitons in kernel
    # sync()
    # run(f'partprobe {drive_path}')
    run(f'sgdisk -Z {drive_path}')


def bootmode_detect() -> str:
    """Detect system boot mode

    Returns:
        str: 'bios' or 'efi'
    """
    if Path('/sys/firmware/efi/').exists():
        return 'efi'
    else:
        return 'bios'


def parttable_create(drive_path: str, root_size: int) -> None:
    """Create a hybrid MBR/GPT partition table
    0-2047 first sectors are free
    2048-4095 sectors - BIOS Boot Partition
    4096 + 256 MB - EFI system partition
    Everything else till the end of a drive - Linux partition

    Args:
        drive_path (str): path to a drive
    """
    if not root_size:
        root_size_text: str = '+100%'
    else:
        root_size_text: str = str(root_size)
    command = f'sgdisk -a1 -n1:2048:4095 -t1:EF02 -n2:4096:+256M -t2:EF00 \
        -n3:0:+{root_size_text}K -t3:8300 {drive_path}'

    run(command)
    # update partitons in kernel
    sync()
    run(f'partprobe {drive_path}')


def filesystem_create(partition: str, fstype: str) -> None:
    """Create a filesystem on a partition

    Args:
        partition (str): path to a partition (for example: '/dev/sda1')
        fstype (str): filesystem type ('efi' or 'ext4')
    """
    if fstype == 'efi':
        command = 'mkfs -t fat -n EFI'
        run(f'{command} {partition}')
    if fstype == 'ext4':
        command = 'mkfs -t ext4 -L persistence'
        run(f'{command} {partition}')


def partition_mount(partition: str,
                    path: str,
                    fsype: str = '',
                    overlay_params: dict[str, str] = {}) -> None:
    """Mount a partition into a path

    Args:
        partition (str): path to a partition (for example: '/dev/sda1')
        path (str): a path where to mount
        fsype (str): optionally, set fstype ('squashfs', 'overlay', 'iso9660')
        overlay_params (dict): optionally, set overlay parameters.
        Defaults to None.
    """
    if fsype in ['squashfs', 'iso9660']:
        command: str = f'mount -o loop,ro -t {fsype} {partition} {path}'
    if fsype == 'overlay' and overlay_params:
        command: str = f'mount -t overlay -o noatime,\
            upperdir={overlay_params["upperdir"]},\
            lowerdir={overlay_params["lowerdir"]},\
            workdir={overlay_params["workdir"]} overlay {path}'

    else:
        command = f'mount {partition} {path}'

    run(command)


def partition_umount(partition: str = '', path: str = '') -> None:
    """Umount a partition by a partition name or a path

    Args:
        partition (str): path to a partition (for example: '/dev/sda1')
        path (str): a path where a partition is mounted
    """
    if partition:
        command = f'umount {partition}'
        run(command)
    if path:
        command = f'umount {path}'
        run(command)


def grub_install(drive_path: str, boot_dir: str, efi_dir: str) -> None:
    """Install GRUB for both BIOS and EFI modes (hybrid boot)

    Args:
        drive_path (str): path to a drive where GRUB must be installed
        boot_dir (str): a path to '/boot' directory
        efi_dir (str): a path to '/boot/efi' directory
    """
    commands: list[str] = [
        f'grub-install --no-floppy --target=i386-pc --boot-directory={boot_dir} \
            {drive_path} --force'                                 ,
        f'grub-install --no-floppy --recheck --target=x86_64-efi \
            --force-extra-removable --boot-directory={boot_dir} \
            --efi-directory={efi_dir} --bootloader-id="VyOS" \
            --no-uefi-secure-boot'
    ]
    for command in commands:
        run(command)


def find_presistence() -> str:
    """Find a mountpoint for persistence storage

    Returns:
        str: Path where 'persistance' pertition is mounted, Empty if not found
    """
    mounted_partitions = disk_partitions()
    for partition in mounted_partitions:
        if partition.mountpoint.endswith('/persistence'):
            return partition.mountpoint
    return ''


def find_device(mountpoint: str) -> str:
    """Find a device by mountpoint

    Returns:
        str: Path to device, Empty if not found
    """
    mounted_partitions = disk_partitions()
    for partition in mounted_partitions:
        if partition.mountpoint == mountpoint:
            return partition.mountpoint
    return ''


def gen_version_uuid(version_name: str) -> str:
    """Generate unique ID from version name

    Use UUID5 / NAMESPACE_URL with prefix `uuid5-`

    Args:
        version_name (str): version name

    Returns:
        str: generated unique ID
    """
    ver_uuid = uuid5(NAMESPACE_URL, version_name)
    ver_id = f'uuid5-{ver_uuid}'
    return ver_id


def grub_version_add(version_name: str,
                     root_dir: str = '',
                     boot_opts: str = '') -> None:
    """Add a new VyOS version to GRUB loader configuration

    Args:
        vyos_version (str): VyOS version name
        root_dir (str): an optional path to the root directory.
        Defaults to empty.
        boot_opts (str): an optional boot options for Linux kernel.
        Defaults to empty.
    """
    if not root_dir:
        root_dir = find_presistence()
    version_config: str = f'{root_dir}/{GRUB_DIR_VYOS_VERS}/{version_name}.cfg'
    render(
        version_config, TMPL_VYOS_VERSION, {
            'version_name': version_name,
            'version_uuid': gen_version_uuid(version_name),
            'boot_opts': boot_opts
        })


def grub_version_del(vyos_version: str, root_dir: str = '') -> None:
    """Delete a VyOS version from GRUB loader configuration

    Args:
        vyos_version (str): VyOS version name
        root_dir (str): an optional path to the root directory.
        Defaults to empty.
    """
    if not root_dir:
        root_dir = find_presistence()
    version_config = f'{root_dir}/{GRUB_DIR_VYOS_VERS}/{vyos_version}.cfg'
    Path(version_config).unlink(missing_ok=True)


def grub_version_list(root_dir: str = '') -> list[str]:
    """Generate a list with installed VyOS versions

    Args:
        root_dir (str): an optional path to the root directory.
        Defaults to empty.

    Returns:
        list: A list with versions names
    """
    if not root_dir:
        root_dir = find_presistence()
    versions_files = Path(f'{root_dir}/{GRUB_DIR_VYOS_VERS}').glob('*.cfg')
    versions_list: list[str] = []
    for file in versions_files:
        versions_list.append(file.stem)
    return versions_list


def grub_read_env(env_file: str = '') -> dict[str, str]:
    """Read GRUB environment

    Args:
        env_file (str, optional): a path to grub environment file.
        Defaults to empty.

    Returns:
        dict: dictionary with GRUB environment
    """
    if not env_file:
        root_dir: str = find_presistence()
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


def grub_get_cfg_ver(root_dir: str = '') -> int:
    """Get current version of GRUB configuration

    Args:
        root_dir (str, optional): an optional path to the root directory.
        Defaults to empty.

    Returns:
        int: a configuration version
    """
    if not root_dir:
        root_dir = find_presistence()

    cfg_ver: Union[str, None] = grub_vars_read(
        f'{root_dir}/{CFG_VYOS_HEADER}').get('VYOS_CFG_VER')
    if cfg_ver:
        cfg_ver_int: int = int(cfg_ver)
    else:
        cfg_ver_int: int = 0
    return cfg_ver_int


def grub_write_cfg_ver(cfg_ver: int, root_dir: str = '') -> None:
    """Write version number of GRUB configuration

    Args:
        cfg_ver (int): a version number to write
        root_dir (str, optional): an optional path to the root directory.
        Defaults to empty.

    Returns:
        int: a configuration version
    """
    if not root_dir:
        root_dir = find_presistence()

    vars_file: str = f'{root_dir}/{CFG_VYOS_HEADER}'
    vars_current: dict[str, str] = grub_vars_read(vars_file)
    vars_current['VYOS_CFG_VER'] = str(cfg_ver)
    grub_vars_write(vars_file, vars_current)


def grub_vars_read(grub_cfg: str) -> dict[str, str]:
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


def grub_modules_read(grub_cfg: str) -> list[str]:
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


def grub_modules_write(grub_cfg: str, mods_list: list[str]) -> None:
    """Write modules list to a GRUB configuration file (overwrite everything)

    Args:
        grub_cfg (str): a path to GRUB configuration file
        mods_list (list): a list with modules to load
    """
    render(grub_cfg, TMPL_GRUB_MODULES, {'mods_list': mods_list})


def grub_vars_write(grub_cfg: str, grub_vars: dict[str, str]) -> None:
    """Write variables to a GRUB configuration file (overwrite everything)

    Args:
        grub_cfg (str): a path to GRUB configuration file
        grub_vars (dict): a dictionary with new variables
    """
    render(grub_cfg, TMPL_GRUB_VARS, {'vars': grub_vars})


def grub_set_default(version_name: str, root_dir: str = '') -> None:
    """Set version as default boot entry

    Args:
        version_name (str): versio name
        root_dir (str, optional): an optional path to the root directory.
        Defaults to empty.
    """
    if not root_dir:
        root_dir = find_presistence()

    vars_file = f'{root_dir}/{CFG_VYOS_VARS}'
    vars_current = grub_vars_read(vars_file)
    vars_current['default'] = gen_version_uuid(version_name)
    grub_vars_write(vars_file, vars_current)


def grub_common_write(root_dir: str = '') -> None:
    """Write common GRUB configuration file (overwrite everything)

    Args:
        root_dir (str, optional): an optional path to the root directory.
        Defaults to empty.
    """
    if not root_dir:
        root_dir = find_presistence()
    common_config = f'{root_dir}/{CFG_VYOS_COMMON}'
    render(common_config, TMPL_GRUB_COMMON, {})


def raid_create(raid_name: str,
                raid_members: list[str],
                raid_level: str = 'raid1') -> None:
    """Create a RAID array

    Args:
        raid_name (str): a name of array (data, backup, test, etc.)
        raid_members (list[str]): a list of array members
        raid_level (str, optional): an array level. Defaults to 'raid1'.
    """
    raid_devices_num: int = len(raid_members)
    raid_members_str: str = ' '.join(raid_members)
    command: str = f'mdadm --create /dev/md/{raid_name} --metadata=1.2 \
        --raid-devices={raid_devices_num} --level={raid_level} \
        {raid_members_str}'

    run(command)


def disks_size() -> dict[str, int]:
    """Get a dictionary with physical disks and their sizes

    Returns:
        dict[str, int]: a dictionary with name: size mapping
    """
    disks_size: dict[str, int] = {}
    lsblk: str = cmd('lsblk -Jbp')
    blk_list = json_loads(lsblk)
    for device in blk_list.get('blockdevices'):
        if device['type'] == 'disk':
            disks_size.update({device['name']: device['size']})
    return disks_size


def image_get_version(image_name: str, root_dir: str) -> str:
    """Extract version name from rootfs based on image name

    Args:
        image_name (str): a name of image (from boot menu)
        root_dir (str): a root directory of persistence storage

    Returns:
        str: version name
    """
    squashfs_file: str = next(
        Path(f'{root_dir}/boot/{image_name}').glob('*.squashfs')).as_posix()
    with TemporaryDirectory() as squashfs_mounted:
        partition_mount(squashfs_file, squashfs_mounted, 'squashfs')
        version_file: str = Path(
            f'{squashfs_mounted}/opt/vyatta/etc/version').read_text()
        partition_umount(squashfs_file)
        version_name: str = version_file.lstrip('Version: ').strip()

    return version_name


def image_details(image_name: str, root_dir: str = '') -> ImageDetails:
    """Return information about image

    Args:
        image_name (str): a name of an image
        root_dir (str, optional): an optional path to the root directory.
        Defaults to ''.

    Returns:
        ImageDetails: a dictionary with details about an image (name, size)
    """
    if not root_dir:
        root_dir = find_presistence()

    image_version: str = image_get_version(image_name, root_dir)

    image_path: Path = Path(f'{root_dir}/boot/{image_name}')
    image_path_rw: Path = Path(f'{root_dir}/boot/{image_name}/rw')

    image_disk_ro: int = int()
    for item in image_path.iterdir():
        if not item.is_symlink():
            image_disk_ro += item.stat().st_size

    image_disk_rw: int = int()
    for item in image_path_rw.rglob('*'):
        if not item.is_symlink():
            image_disk_rw += item.stat().st_size

    image_details: ImageDetails = {
        'name': image_name,
        'version': image_version,
        'disk_ro': image_disk_ro,
        'disk_rw': image_disk_rw,
        'disk_total': image_disk_ro + image_disk_rw
    }

    return image_details


def get_running_image() -> str:
    """Find currently running image name

    Returns:
        str: image name
    """
    running_image: str = ''
    regex_filter = re_compile(REGEX_KERNEL_CMDLINE)
    cmdline: str = Path('/proc/cmdline').read_text()
    running_image_result = regex_filter.match(cmdline)
    if running_image_result:
        running_image: str = running_image_result.groupdict().get(
            'image_version', '')
    # we need to have a fallbak for live systems
    if not running_image:
        running_image: str = version.get_version()

    return running_image


def get_default_image(root_dir: str = '') -> str:
    """Get default boot entry

    Args:
        root_dir (str, optional): an optional path to the root directory.
        Defaults to empty.
    Returns:
        str: a version name
    """
    if not root_dir:
        root_dir = find_presistence()

    vars_file: str = f'{root_dir}/{CFG_VYOS_VARS}'
    vars_current: dict[str, str] = grub_vars_read(vars_file)
    default_uuid: str = vars_current.get('default', '')
    if default_uuid:
        images_list: list[str] = Grub.grub_version_list(root_dir)
        for image_name in images_list:
            if default_uuid == gen_version_uuid(image_name):
                return image_name
        return ''
    else:
        return ''


def image_name_validate(image_name: str) -> bool:
    """Validate image name

    Args:
        image_name (str): suggested image name

    Returns:
        bool: validation result
    """
    regex_filter = re_compile(r'^[\w\.+-]{1,32}$')
    if regex_filter.match(image_name):
        return True
    return False


def is_live_boot() -> bool:
    """Detect live booted system

    Returns:
        bool: True if the system currently booted in live mode
    """
    regex_filter = re_compile(REGEX_KERNEL_CMDLINE)
    cmdline: str = Path('/proc/cmdline').read_text()
    running_image_result = regex_filter.match(cmdline)
    if running_image_result:
        boot_type: str = running_image_result.groupdict().get('boot_type', '')
        if boot_type == 'live':
            return True
    return False


def create_grub_structure(root_dir: str = '') -> None:
    """Create GRUB directories structure

    Args:
        root_dir (str, optional): an optional path to the root directory.
        Defaults to ''.
    """
    if not root_dir:
        root_dir = find_presistence()

    Path(f'{root_dir}/GRUB_DIR_VYOS_VERS').mkdir(parents=True, exist_ok=True)
