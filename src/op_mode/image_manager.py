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
from shutil import rmtree
from sys import exit

from vyos.system import disk, grub, image
from vyos.util import ask_yes_no


def delete_image(image_name: str) -> None:
    """Remove installed image files and boot entry

    Args:
        image_name (str): a name of image to delete
    """
    if image_name == image.get_running_image():
        exit('Currently running image cannot be deleted')
    if image_name == image.get_default_image():
        exit('Default image cannot be deleted')
    available_images: list[str] = grub.version_list()
    if image_name not in available_images:
        exit(f'The image "{image_name}" cannot be found')
    presistence_storage: str = disk.find_persistence()
    if not presistence_storage:
        exit('Persistence storage cannot be found')

    if not ask_yes_no(f'Do you really want to delete the image {image_name}?',
                      default=False):
        exit()

    # remove files and menu entry
    version_path: Path = Path(f'{presistence_storage}/boot/{image_name}')
    try:
        rmtree(version_path)
        grub.version_del(image_name, presistence_storage)
        print(f'The image "{image_name}" was successfully deleted')
    except Exception as err:
        exit(f'Unable to remove the image "{image_name}": {err}')


def set_image(image_name: str) -> None:
    """Set default boot image

    Args:
        image_name (str): an image name
    """
    if image_name == image.get_default_image():
        exit(f'The image "{image_name}" already configured as default')
    available_images: list[str] = grub.version_list()
    if image_name not in available_images:
        exit(f'The image "{image_name}" cannot be found')
    presistence_storage: str = disk.find_persistence()
    if not presistence_storage:
        exit('Persistence storage cannot be found')

    if not ask_yes_no(
            f'Do you really want to set the image {image_name} '
            'as default boot image?',
            default=False):
        exit()

    # set default boot image
    try:
        grub.set_default(image_name, presistence_storage)
        print(f'The image "{image_name}" is now default boot image')
    except Exception as err:
        exit(f'Unable to set default image "{image_name}": {err}')


def rename_image(name_old: str, name_new: str) -> None:
    """Rename installed image

    Args:
        name_old (str): old name
        name_new (str): new name
    """
    if name_old == image.get_running_image():
        exit('Currently running image cannot be renamed')
    available_images: list[str] = grub.version_list()
    if name_old not in available_images:
        exit(f'The image "{name_old}" cannot be found')
    if name_new in available_images:
        exit(f'The image "{name_new}" already exists')
    if not image.validate_name(name_new):
        exit(f'The image name "{name_new}" is not allowed')

    presistence_storage: str = disk.find_persistence()
    if not presistence_storage:
        exit('Persistence storage cannot be found')

    if not ask_yes_no(
            f'Do you really want to rename the image {name_old} '
            f'to the {name_new}?',
            default=False):
        exit()

    try:
        # replace default boot item
        if name_old == image.get_default_image():
            grub.set_default(name_new, presistence_storage)

        # rename files and dirs
        old_path: Path = Path(f'{presistence_storage}/boot/{name_old}')
        new_path: Path = Path(f'{presistence_storage}/boot/{name_new}')
        old_path.rename(new_path)

        # replace boot item
        grub.version_del(name_old, presistence_storage)
        grub.version_add(name_new, presistence_storage)

        print(f'The image "{name_old}" was renamed to "{name_new}"')
    except Exception as err:
        exit(f'Unable to rename image "{name_old}" to "{name_new}": {err}')


def list_images() -> None:
    """Print list of available images for CLI hints"""
    images_list: list[str] = grub.version_list()
    for image_name in images_list:
        print(image_name)


def parse_arguments() -> Namespace:
    """Parse arguments

    Returns:
        Namespace: a namespace with parsed arguments
    """
    parser: ArgumentParser = ArgumentParser(description='Manage system images')
    parser.add_argument('--action',
                        choices=['delete', 'set', 'rename', 'list'],
                        required=True,
                        help='action to perform with an image')
    parser.add_argument(
        '--image_name',
        help=
        'a name of an image to add, delete, install, rename, or set as default')
    parser.add_argument('--image_new_name', help='a new name for image')
    args: Namespace = parser.parse_args()
    # Validate arguments
    if args.action == 'delete' and not args.image_name:
        exit('An image name is required for delete action')
    if args.action == 'set' and not args.image_name:
        exit('An image name is required for set action')
    if args.action == 'rename' and (not args.image_name or
                                    not args.image_new_name):
        exit('Both old and new image names are required for rename action')

    return args


if __name__ == '__main__':
    try:
        args: Namespace = parse_arguments()
        if args.action == 'delete':
            delete_image(args.image_name)
        if args.action == 'set':
            set_image(args.image_name)
        if args.action == 'rename':
            rename_image(args.image_name, args.image_new_name)
        if args.action == 'list':
            list_images()

        exit()

    except KeyboardInterrupt:
        print('Stopped by Ctrl+C')
        exit()

    except Exception as err:
        exit(f'{err}')
