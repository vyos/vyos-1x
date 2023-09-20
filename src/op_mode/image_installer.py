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

from argparse import ArgumentParser, Namespace
from pathlib import Path
from shutil import copy, chown, rmtree, copytree
from sys import exit
from passlib.hosts import linux_context
from urllib.parse import urlparse

from psutil import disk_partitions

from vyos.configtree import ConfigTree
from vyos.remote import download
from vyos.system import disk, grub, image
from vyos.template import render
from vyos.utils.io import ask_input, ask_yes_no
from vyos.utils.file import chmod_2775
from vyos.utils.process import run

# define text messages
MSG_ERR_NOT_LIVE: str = 'The system is already installed. Please use "add system image" instead.'
MSG_ERR_LIVE: str = 'The system is in live-boot mode. Please use "install image" instead.'
MSG_ERR_NO_DISK: str = 'No suitable disk was found. There must be at least one disk of 2GB or greater size.'
MSG_INFO_INSTALL_WELCOME: str = 'Welcome to VyOS installation!\nThis command will install the VyOS to your permanent storage.'
MSG_INFO_INSTALL_EXIT: str = 'Exitting from VyOS installation'
MSG_INFO_INSTALL_SUCCESS: str = 'The image installed successfully; please reboot now.'
MSG_INFO_INSTALL_DISKS_LIST: str = 'Were found the next disks:'
MSG_INFO_INSTALL_DISK_SELECT: str = 'Which one should be used for installation?'
MSG_INFO_INSTALL_DISK_CONFIRM: str = 'Installation will delete all data on the drive. Continue?'
MSG_INFO_INSTALL_PARTITONING: str = 'Creating partition table...'
MSG_INPUT_CONFIG_FOUND: str = 'An active configuration was found. Would you like to copy it to the new image?'
MSG_INPUT_IMAGE_NAME: str = 'What would you like to name this image?'
MSG_INPUT_IMAGE_DEFAULT: str = 'Would you like to set a new image as default one for boot?'
MSG_INPUT_PASSWORD: str = 'Please enter a password for the "vyos" user'
MSG_INPUT_ROOT_SIZE_ALL: str = 'Would you like to use all free space on the drive?'
MSG_INPUT_ROOT_SIZE_SET: str = 'What should be a size (in GB) of the root partition (min is 1.5 GB)?'
MSG_INPUT_CONSOLE_TYPE: str = 'What console should be used by default? (K: KVM, S: Serial, U: USB-Serial)?'
MSG_WARN_ISO_SIGN_INVALID: str = 'Signature is not valid. Do you want to continue with installation?'
MSG_WARN_ISO_SIGN_UNAVAL: str = 'Signature is not available. Do you want to continue with installation?'
MSG_WARN_ROOT_SIZE_TOOBIG: str = 'The size is too big. Try again.'
MSG_WARN_ROOT_SIZE_TOOSMALL: str = 'The size is too small. Try again'
MSG_WARN_IMAGE_NAME_WRONG: str = 'The suggested name is unsupported!\n'
'It must be between 1 and 32 characters long and contains only the next characters: .+-_ a-z A-Z 0-9'
CONST_MIN_DISK_SIZE: int = 2147483648  # 2 GB
CONST_MIN_ROOT_SIZE: int = 1610612736  # 1.5 GB
# a reserved space: 2MB for header, 1 MB for BIOS partition, 256 MB for EFI
CONST_RESERVED_SPACE: int = (2 + 1 + 256) * 1024**2

# define directories and paths
DIR_INSTALLATION: str = '/mnt/installation'
DIR_ROOTFS_SRC: str = f'{DIR_INSTALLATION}/root_src'
DIR_ROOTFS_DST: str = f'{DIR_INSTALLATION}/root_dst'
DIR_ISO_MOUNT: str = f'{DIR_INSTALLATION}/iso_src'
DIR_DST_ROOT: str = f'{DIR_INSTALLATION}/disk_dst'
DIR_KERNEL_SRC: str = '/boot/'
FILE_ROOTFS_SRC: str = '/usr/lib/live/mount/medium/live/filesystem.squashfs'
ISO_DOWNLOAD_PATH: str = '/tmp/vyos_installation.iso'

# default boot variables
DEFAULT_BOOT_VARS: dict[str, str] = {
    'timeout': '5',
    'console_type': 'tty',
    'console_num': '0',
    'bootmode': 'normal'
}


def bytes_to_gb(size: int) -> float:
    """Convert Bytes to GBytes, rounded to 1 decimal number

    Args:
        size (int): input size in bytes

    Returns:
        float: size in GB
    """
    return round(size / 1024**3, 1)


def gb_to_bytes(size: float) -> int:
    """Convert GBytes to Bytes

    Args:
        size (float): input size in GBytes

    Returns:
        int: size in bytes
    """
    return int(size * 1024**3)


def find_disk() -> tuple[str, int]:
    """Find a target disk for installation

    Returns:
        tuple[str, int]: disk name and size in bytes
    """
    # check for available disks
    disks_available: dict[str, int] = disk.disks_size()
    for disk_name, disk_size in disks_available.copy().items():
        if disk_size < CONST_MIN_DISK_SIZE:
            del disks_available[disk_name]
    if not disks_available:
        print(MSG_ERR_NO_DISK)
        exit(MSG_INFO_INSTALL_EXIT)

    # select one as a target
    print(MSG_INFO_INSTALL_DISKS_LIST)
    default_disk: str = list(disks_available)[0]
    for disk_name, disk_size in disks_available.items():
        disk_size_human: str = bytes_to_gb(disk_size)
        print(f'Drive: {disk_name} ({disk_size_human} GB)')
    disk_selected: str = ask_input(MSG_INFO_INSTALL_DISK_SELECT,
                                   default=default_disk,
                                   valid_responses=list(disks_available))

    return disk_selected, disks_available[disk_selected]


def ask_root_size(available_space: int) -> int:
    """Define a size of root partition

    Args:
        available_space (int): available space in bytes for a root partition

    Returns:
        int: defined size
    """
    if ask_yes_no(MSG_INPUT_ROOT_SIZE_ALL, default=True):
        return available_space

    while True:
        root_size_gb: str = ask_input(MSG_INPUT_ROOT_SIZE_SET)
        root_size_kbytes: int = (gb_to_bytes(float(root_size_gb))) // 1024

        if root_size_kbytes > available_space:
            print(MSG_WARN_ROOT_SIZE_TOOBIG)
            continue
        if root_size_kbytes < CONST_MIN_ROOT_SIZE / 1024:
            print(MSG_WARN_ROOT_SIZE_TOOSMALL)
            continue

        return root_size_kbytes


def prepare_tmp_disr() -> None:
    """Create temporary directories for installation
    """
    print('Creating temporary directories')
    for dir in [DIR_ROOTFS_SRC, DIR_ROOTFS_DST, DIR_DST_ROOT]:
        dirpath = Path(dir)
        dirpath.mkdir(mode=0o755, parents=True)


def setup_grub(root_dir: str) -> None:
    """Install GRUB configurations

    Args:
        root_dir (str): a path to the root of target filesystem
    """
    print('Installing GRUB configuration files')
    grub_cfg_main = f'{root_dir}/{grub.GRUB_DIR_MAIN}/grub.cfg'
    grub_cfg_vars = f'{root_dir}/{grub.CFG_VYOS_VARS}'
    grub_cfg_modules = f'{root_dir}/{grub.CFG_VYOS_MODULES}'
    grub_cfg_menu = f'{root_dir}/{grub.CFG_VYOS_MENU}'
    grub_cfg_options = f'{root_dir}/{grub.CFG_VYOS_OPTIONS}'

    # create new files
    render(grub_cfg_main, grub.TMPL_GRUB_MAIN, {})
    grub.common_write(root_dir)
    grub.vars_write(grub_cfg_vars, DEFAULT_BOOT_VARS)
    grub.modules_write(grub_cfg_modules, [])
    grub.write_cfg_ver(1, root_dir)
    render(grub_cfg_menu, grub.TMPL_GRUB_MENU, {})
    render(grub_cfg_options, grub.TMPL_GRUB_OPTS, {})


def configure_authentication(config_file: str, password: str) -> None:
    """Write encrypted password to config file

    Args:
        config_file (str): path of target config file
        password (str): plaintext password

    N.B. this can not be deferred by simply setting the plaintext password
    and relying on the config mode script to process at boot, as the config
    will not automatically be saved in that case, thus leaving the
    plaintext exposed
    """
    encrypted_password = linux_context.hash(password)

    with open(config_file) as f:
        config_string = f.read()

    config = ConfigTree(config_string)
    config.set([
        'system', 'login', 'user', 'vyos', 'authentication',
        'encrypted-password'
    ],
               value=encrypted_password,
               replace=True)
    config.set_tag(['system', 'login', 'user'])

    with open(config_file, 'w') as f:
        f.write(config.to_string())

def validate_signature(file_path: str, sign_type: str) -> None:
    """Validate a file by signature and delete a signature file

    Args:
        file_path (str): a path to file
        sign_type (str): a signature type
    """
    print('Validating signature')
    signature_valid: bool = False
    # validate with minisig
    if sign_type == 'minisig':
        for pubkey in [
                '/usr/share/vyos/keys/vyos-release.minisign.pub',
                '/usr/share/vyos/keys/vyos-backup.minisign.pub'
        ]:
            if run(f'minisign -V -q -p {pubkey} -m {file_path} -x {file_path}.minisig'
                  ) == 0:
                signature_valid = True
                break
        Path(f'{file_path}.minisig').unlink()
    # validate with GPG
    if sign_type == 'asc':
        if run(f'gpg --verify ${file_path}.asc ${file_path}') == 0:
            signature_valid = True
        Path(f'{file_path}.asc').unlink()

    # warn or pass
    if not signature_valid:
        if not ask_yes_no(MSG_WARN_ISO_SIGN_INVALID, default=False):
            exit(MSG_INFO_INSTALL_EXIT)
    else:
        print('Signature is valid')


def image_fetch(image_path: str) -> Path:
    """Fetch an ISO image

    Args:
        image_path (str): a path, remote or local

    Returns:
        Path: a path to a local file
    """
    try:
        # check a type of path
        if urlparse(image_path).scheme:
            # download an image
            download(ISO_DOWNLOAD_PATH, image_path, True, True)
            # download a signature
            sign_file = (False, '')
            for sign_type in ['minisig', 'asc']:
                try:
                    download(f'{ISO_DOWNLOAD_PATH}.{sign_type}',
                             f'{image_path}.{sign_type}')
                    sign_file = (True, sign_type)
                    break
                except Exception:
                    print(f'{sign_type} signature is not available')
            # validate a signature if it is available
            if sign_file[0]:
                validate_signature(ISO_DOWNLOAD_PATH, sign_file[1])
            else:
                if not ask_yes_no(MSG_WARN_ISO_SIGN_UNAVAL, default=False):
                    cleanup()
                    exit(MSG_INFO_INSTALL_EXIT)

            return Path(ISO_DOWNLOAD_PATH)
        else:
            local_path: Path = Path(image_path)
            if local_path.is_file():
                return local_path
            else:
                raise
    except Exception:
        print(f'The image cannot be fetched from: {image_path}')
        exit(1)


def migrate_config() -> bool:
    """Check for active config and ask user for migration

    Returns:
        bool: user's decision
    """
    active_config_path: Path = Path('/opt/vyatta/etc/config/config.boot')
    if active_config_path.exists():
        if ask_yes_no(MSG_INPUT_CONFIG_FOUND, default=True):
            return True
    return False


def cleanup(mounts: list[str] = [], remove_items: list[str] = []) -> None:
    """Clean up after installation

    Args:
        mounts (list[str], optional): List of mounts to unmount.
        Defaults to [].
        remove_items (list[str], optional): List of files or directories
        to remove. Defaults to [].
    """
    print('Cleaning up')
    # clean up installation directory by default
    mounts_all = disk_partitions(all=True)
    for mounted_device in mounts_all:
        if mounted_device.mountpoint.startswith(DIR_INSTALLATION) and not (
                mounted_device.device in mounts or
                mounted_device.mountpoint in mounts):
            mounts.append(mounted_device.mountpoint)
    # add installation dir to cleanup list
    if DIR_INSTALLATION not in remove_items:
        remove_items.append(DIR_INSTALLATION)
    # also delete an ISO file
    if Path(ISO_DOWNLOAD_PATH).exists(
    ) and ISO_DOWNLOAD_PATH not in remove_items:
        remove_items.append(ISO_DOWNLOAD_PATH)

    if mounts:
        print('Unmounting target filesystems')
        for mountpoint in mounts:
            disk.partition_umount(mountpoint)
    if remove_items:
        print('Removing temporary files')
        for remove_item in remove_items:
            if Path(remove_item).exists():
                if Path(remove_item).is_file():
                    Path(remove_item).unlink()
                if Path(remove_item).is_dir():
                    rmtree(remove_item)


def install_image() -> None:
    """Install an image to a disk
    """
    if not image.is_live_boot():
        exit(MSG_ERR_NOT_LIVE)

    print(MSG_INFO_INSTALL_WELCOME)
    if not ask_yes_no('Would you like to continue?'):
        print(MSG_INFO_INSTALL_EXIT)
        exit()

    try:
        # configure image name
        running_image_name: str = image.get_running_image()
        while True:
            image_name: str = ask_input(MSG_INPUT_IMAGE_NAME,
                                        running_image_name)
            if image.validate_name(image_name):
                break
            print(MSG_WARN_IMAGE_NAME_WRONG)

        # define target drive
        install_target, target_size = find_disk()

        # define target rootfs size in KB (smallest unit acceptable by sgdisk)
        availabe_size: int = (target_size - CONST_RESERVED_SPACE) // 1024
        rootfs_size: int = ask_root_size(availabe_size)

        # ask for password
        user_password: str = ask_input(MSG_INPUT_PASSWORD, default='vyos')

        # ask for default console
        console_type: str = ask_input(MSG_INPUT_CONSOLE_TYPE,
                                      default='K',
                                      valid_responses=['K', 'S', 'U'])
        console_dict: dict[str, str] = {'K': 'tty', 'S': 'ttyS', 'U': 'ttyUSB'}

        # create partitions
        if not ask_yes_no(MSG_INFO_INSTALL_DISK_CONFIRM):
            print(MSG_INFO_INSTALL_EXIT)
            exit()
        print(MSG_INFO_INSTALL_PARTITONING)
        disk.disk_cleanup(install_target)
        disk.parttable_create(install_target, rootfs_size)
        disk.filesystem_create(f'{install_target}2', 'efi')
        disk.filesystem_create(f'{install_target}3', 'ext4')

        # create directiroes for installation media
        prepare_tmp_disr()

        # mount target filesystem and create required dirs inside
        print('Mounting new partitions')
        disk.partition_mount(f'{install_target}3', DIR_DST_ROOT)
        Path(f'{DIR_DST_ROOT}/boot/efi').mkdir(parents=True)
        disk.partition_mount(f'{install_target}2', f'{DIR_DST_ROOT}/boot/efi')

        # a config dir. It is the deepest one, so the comand will
        # create all the rest in a single step
        print('Creating a configuration file')
        target_config_dir: str = f'{DIR_DST_ROOT}/boot/{image_name}/rw/opt/vyatta/etc/config/'
        Path(target_config_dir).mkdir(parents=True)
        chown(target_config_dir, group='vyattacfg')
        chmod_2775(target_config_dir)
        # copy config
        copy('/opt/vyatta/etc/config/config.boot', target_config_dir)
        configure_authentication(f'{target_config_dir}/config.boot',
                                 user_password)
        Path(f'{target_config_dir}/.vyatta_config').touch()

        # create a persistence.conf
        Path(f'{DIR_DST_ROOT}/persistence.conf').write_text('/ union\n')

        # copy system image and kernel files
        print('Copying system image files')
        for file in Path(DIR_KERNEL_SRC).iterdir():
            if file.is_file():
                copy(file, f'{DIR_DST_ROOT}/boot/{image_name}/')
        copy(FILE_ROOTFS_SRC,
             f'{DIR_DST_ROOT}/boot/{image_name}/{image_name}.squashfs')

        # install GRUB
        print('Installing GRUB to the drive')
        grub.install(install_target, f'{DIR_DST_ROOT}/boot/',
                     f'{DIR_DST_ROOT}/boot/efi')
        setup_grub(DIR_DST_ROOT)
        # add information about version
        grub.create_structure()
        grub.version_add(image_name, DIR_DST_ROOT)
        grub.set_default(image_name, DIR_DST_ROOT)
        grub.set_console_type(console_dict[console_type], DIR_DST_ROOT)

        # umount filesystems and remove temporary files
        cleanup([f'{install_target}2', f'{install_target}3'],
                ['/mnt/installation'])

        # we are done
        print(MSG_INFO_INSTALL_SUCCESS)
        exit()

    except Exception as err:
        print(f'Unable to install VyOS: {err}')
        # unmount filesystems and clenup
        try:
            cleanup([f'{install_target}2', f'{install_target}3'],
                    ['/mnt/installation'])
        except Exception as err:
            print(f'Cleanup failed: {err}')

        exit(1)


def add_image(image_path: str) -> None:
    """Add a new image

    Args:
        image_path (str): a path to an ISO image
    """
    if image.is_live_boot():
        exit(MSG_ERR_LIVE)

    # fetch an image
    iso_path: Path = image_fetch(image_path)
    try:
        # mount an ISO
        Path(DIR_ISO_MOUNT).mkdir(mode=0o755, parents=True)
        disk.partition_mount(iso_path, DIR_ISO_MOUNT, 'iso9660')

        # check sums
        print('Validating image checksums')
        if run(f'cd {DIR_ISO_MOUNT} && sha256sum --status -c sha256sum.txt'):
            cleanup()
            exit('Image checksum verification failed.')

        # mount rootfs (to get a system version)
        Path(DIR_ROOTFS_SRC).mkdir(mode=0o755, parents=True)
        disk.partition_mount(f'{DIR_ISO_MOUNT}/live/filesystem.squashfs',
                             DIR_ROOTFS_SRC, 'squashfs')
        version_file: str = Path(
            f'{DIR_ROOTFS_SRC}/opt/vyatta/etc/version').read_text()
        disk.partition_umount(f'{DIR_ISO_MOUNT}/live/filesystem.squashfs')
        version_name: str = version_file.lstrip('Version: ').strip()
        image_name: str = ask_input(MSG_INPUT_IMAGE_NAME, version_name)
        set_as_default: bool = ask_yes_no(MSG_INPUT_IMAGE_DEFAULT, default=True)

        # find target directory
        root_dir: str = disk.find_persistence()

        # a config dir. It is the deepest one, so the comand will
        # create all the rest in a single step
        target_config_dir: str = f'{root_dir}/boot/{image_name}/rw/opt/vyatta/etc/config/'
        # copy config
        if migrate_config():
            print('Copying configuration directory')
            # copytree preserves perms but not ownership:
            Path(target_config_dir).mkdir(parents=True)
            chown(target_config_dir, group='vyattacfg')
            chmod_2775(target_config_dir)
            copytree('/opt/vyatta/etc/config/', target_config_dir,
                     dirs_exist_ok=True)
        else:
            Path(target_config_dir).mkdir(parents=True)
            chown(target_config_dir, group='vyattacfg')
            chmod_2775(target_config_dir)
            Path(f'{target_config_dir}/.vyatta_config').touch()

        # copy system image and kernel files
        print('Copying system image files')
        for file in Path(f'{DIR_ISO_MOUNT}/live').iterdir():
            if file.is_file() and (file.match('initrd*') or
                                   file.match('vmlinuz*')):
                copy(file, f'{root_dir}/boot/{image_name}/')
        copy(f'{DIR_ISO_MOUNT}/live/filesystem.squashfs',
             f'{root_dir}/boot/{image_name}/{image_name}.squashfs')

        # unmount an ISO and cleanup
        cleanup([str(iso_path)])

        # add information about version
        grub.version_add(image_name, root_dir)
        if set_as_default:
            grub.set_default(image_name, root_dir)

    except Exception as err:
        # unmount an ISO and cleanup
        cleanup([str(iso_path)])
        exit(f'Whooops: {err}')


def parse_arguments() -> Namespace:
    """Parse arguments

    Returns:
        Namespace: a namespace with parsed arguments
    """
    parser: ArgumentParser = ArgumentParser(
        description='Install new system images')
    parser.add_argument('--action',
                        choices=['install', 'add'],
                        required=True,
                        help='action to perform with an image')
    parser.add_argument(
        '--image_path',
        help='a path (HTTP or local file) to an image that needs to be installed'
    )
    # parser.add_argument('--image_new_name', help='a new name for image')
    args: Namespace = parser.parse_args()
    # Validate arguments
    if args.action == 'add' and not args.image_path:
        exit('A path to image is required for add action')

    return args


if __name__ == '__main__':
    try:
        args: Namespace = parse_arguments()
        if args.action == 'install':
            install_image()
        if args.action == 'add':
            add_image(args.image_path)

        exit()

    except KeyboardInterrupt:
        print('Stopped by Ctrl+C')
        cleanup()
        exit()

    except Exception as err:
        exit(f'{err}')
