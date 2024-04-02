#!/usr/bin/env python3
#
# Copyright 2023-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

import sys
from typing import Union

from tabulate import tabulate

from vyos import opmode
from vyos.system import disk
from vyos.system import grub
from vyos.system import image
from vyos.utils.convert import bytes_to_human


def _format_show_images_summary(images_summary: image.BootDetails) -> str:
    headers: list[str] = ['Name', 'Default boot', 'Running']
    table_data: list[list[str]] = list()
    for image_item in images_summary.get('images_available', []):
        name: str = image_item
        if images_summary.get('image_default') == name:
            default: str = 'Yes'
        else:
            default: str = ''

        if images_summary.get('image_running') == name:
            running: str = 'Yes'
        else:
            running: str = ''

        table_data.append([name, default, running])
    tabulated: str = tabulate(table_data, headers)

    return tabulated


def _format_show_images_details(
        images_details: list[image.ImageDetails]) -> str:
    headers: list[str] = [
        'Name', 'Version', 'Storage Read-Only', 'Storage Read-Write',
        'Storage Total'
    ]
    table_data: list[list[Union[str, int]]] = list()
    for image_item in images_details:
        name: str = image_item.get('name')
        version: str = image_item.get('version')
        disk_ro: str = bytes_to_human(image_item.get('disk_ro'),
                                      precision=1, int_below_exponent=30)
        disk_rw: str = bytes_to_human(image_item.get('disk_rw'),
                                      precision=1, int_below_exponent=30)
        disk_total: str = bytes_to_human(image_item.get('disk_total'),
                                         precision=1, int_below_exponent=30)
        table_data.append([name, version, disk_ro, disk_rw, disk_total])
    tabulated: str = tabulate(table_data, headers,
                              colalign=('left', 'left', 'right', 'right', 'right'))

    return tabulated


def show_images_summary(raw: bool) -> Union[image.BootDetails, str]:
    images_available: list[str] = grub.version_list()
    root_dir: str = disk.find_persistence()
    boot_vars: dict = grub.vars_read(f'{root_dir}/{image.CFG_VYOS_VARS}')

    images_summary: image.BootDetails = dict()

    images_summary['image_default'] = image.get_default_image()
    images_summary['image_running'] = image.get_running_image()
    images_summary['images_available'] = images_available
    images_summary['console_type'] = boot_vars.get('console_type')
    images_summary['console_num'] = boot_vars.get('console_num')

    if raw:
        return images_summary
    else:
        return _format_show_images_summary(images_summary)


def show_images_details(raw: bool) -> Union[list[image.ImageDetails], str]:
    images_details = image.get_images_details()

    if raw:
        return images_details
    else:
        return _format_show_images_details(images_details)


if __name__ == '__main__':
    try:
        res = opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, opmode.Error) as e:
        print(e)
        sys.exit(1)
