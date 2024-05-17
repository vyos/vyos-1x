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

from pathlib import Path
from re import compile as re_compile
from functools import wraps
from tempfile import TemporaryDirectory
from typing import TypedDict
from json import loads

from vyos.defaults import directories
from vyos.system import disk, grub

# Define variables
GRUB_DIR_MAIN: str = '/boot/grub'
GRUB_DIR_VYOS: str = f'{GRUB_DIR_MAIN}/grub.cfg.d'
CFG_VYOS_VARS: str = f'{GRUB_DIR_VYOS}/20-vyos-defaults-autoload.cfg'
GRUB_DIR_VYOS_VERS: str = f'{GRUB_DIR_VYOS}/vyos-versions'
# prepare regexes
REGEX_KERNEL_CMDLINE: str = r'^BOOT_IMAGE=/(?P<boot_type>boot|live)/((?P<image_version>.+)/)?vmlinuz.*$'
REGEX_SYSTEM_CFG_VER: str = r'(\r\n|\r|\n)SYSTEM_CFG_VER\s*=\s*(?P<cfg_ver>\d+)(\r\n|\r|\n)'


# structures definitions
class ImageDetails(TypedDict):
    name: str
    version: str
    tools_version: int
    disk_ro: int
    disk_rw: int
    disk_total: int


class BootDetails(TypedDict):
    image_default: str
    image_running: str
    images_available: list[str]
    console_type: str
    console_num: int


def bootmode_detect() -> str:
    """Detect system boot mode

    Returns:
        str: 'bios' or 'efi'
    """
    if Path('/sys/firmware/efi/').exists():
        return 'efi'
    else:
        return 'bios'


def get_image_version(mount_path: str) -> str:
    """Extract version name from rootfs mounted at mount_path

    Args:
        mount_path (str): mount path of rootfs

    Returns:
        str: version name
    """
    version_file: str = Path(
        f'{mount_path}/opt/vyatta/etc/version').read_text()
    version_name: str = version_file.lstrip('Version: ').strip()

    return version_name


def get_image_tools_version(mount_path: str) -> int:
    """Extract image-tools version from rootfs mounted at mount_path

    Args:
        mount_path (str): mount path of rootfs

    Returns:
        str: image-tools version
    """
    try:
        version_file: str = Path(
            f'{mount_path}/usr/lib/python3/dist-packages/vyos/system/__init__.py').read_text()
    except FileNotFoundError:
        system_cfg_ver: int = 0
    else:
        res = re_compile(REGEX_SYSTEM_CFG_VER).search(version_file)
        system_cfg_ver: int = int(res.groupdict().get('cfg_ver', 0))

    return system_cfg_ver


def get_versions(image_name: str, root_dir: str = '') -> dict[str, str]:
    """Return versions of image and image-tools

    Args:
        image_name (str): a name of an image
        root_dir (str, optional): an optional path to the root directory.
        Defaults to ''.

    Returns:
        dict[str, int]: a dictionary with versions of image and image-tools
    """
    if not root_dir:
        root_dir = disk.find_persistence()

    squashfs_file: str = next(
        Path(f'{root_dir}/boot/{image_name}').glob('*.squashfs')).as_posix()
    with TemporaryDirectory() as squashfs_mounted:
        disk.partition_mount(squashfs_file, squashfs_mounted, 'squashfs')

        image_version: str = get_image_version(squashfs_mounted)
        image_tools_version: int = get_image_tools_version(squashfs_mounted)

        disk.partition_umount(squashfs_file)

    versions: dict[str, int] = {
        'image': image_version,
        'image-tools': image_tools_version
    }

    return versions


def get_details(image_name: str, root_dir: str = '') -> ImageDetails:
    """Return information about image

    Args:
        image_name (str): a name of an image
        root_dir (str, optional): an optional path to the root directory.
        Defaults to ''.

    Returns:
        ImageDetails: a dictionary with details about an image (name, size)
    """
    if not root_dir:
        root_dir = disk.find_persistence()

    versions = get_versions(image_name, root_dir)
    image_version: str = versions.get('image', '')
    image_tools_version: int = versions.get('image-tools', 0)

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
        'tools_version': image_tools_version,
        'disk_ro': image_disk_ro,
        'disk_rw': image_disk_rw,
        'disk_total': image_disk_ro + image_disk_rw
    }

    return image_details


def get_images_details() -> list[ImageDetails]:
    """Return information about all images

    Returns:
        list[ImageDetails]: a list of dictionaries with details about images
    """
    images: list[str] = grub.version_list()
    images_details: list[ImageDetails] = list()
    for image_name in images:
        images_details.append(get_details(image_name))

    return images_details


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
    # we need to have a fallback for live systems:
    # explicit read from version file
    if not running_image:
        json_data: str = Path(directories['data']).joinpath('version.json').read_text()
        dict_data: dict = loads(json_data)
        running_image: str = dict_data['version']

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
        root_dir = disk.find_persistence()

    vars_file: str = f'{root_dir}/{CFG_VYOS_VARS}'
    vars_current: dict[str, str] = grub.vars_read(vars_file)
    default_uuid: str = vars_current.get('default', '')
    if default_uuid:
        images_list: list[str] = grub.version_list(root_dir)
        for image_name in images_list:
            if default_uuid == grub.gen_version_uuid(image_name):
                return image_name
        return ''
    else:
        return ''


def validate_name(image_name: str) -> bool:
    """Validate image name

    Args:
        image_name (str): suggested image name

    Returns:
        bool: validation result
    """
    regex_filter = re_compile(r'^[\w\.+-]{1,64}$')
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
        if boot_type == 'boot':
            return False
    return True

def if_not_live_boot(func):
    """Decorator to call function only if not live boot"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not is_live_boot():
            ret = func(*args, **kwargs)
            return ret
        return None
    return wrapper

def is_running_as_container() -> bool:
    if Path('/.dockerenv').exists():
        return True
    return False
