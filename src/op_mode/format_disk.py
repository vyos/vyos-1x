#!/usr/bin/env python3
#
# Copyright (C) 2019-2021 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import os
import re

from datetime import datetime

from vyos.utils.io import ask_yes_no
from vyos.utils.process import call
from vyos.utils.process import cmd
from vyos.utils.process import DEVNULL
from vyos.utils.disk import device_from_id

def list_disks():
    disks = set()
    with open('/proc/partitions') as partitions_file:
        for line in partitions_file:
            fields = line.strip().split()
            if len(fields) == 4 and fields[3].isalpha() and fields[3] != 'name':
                disks.add(fields[3])
    return disks


def is_busy(disk: str):
    """Check if given disk device is busy by re-reading it's partition table"""
    return call(f'blockdev --rereadpt /dev/{disk}', stderr=DEVNULL) != 0


def backup_partitions(disk: str):
    """Save sfdisk partitions output to a backup file"""

    device_path = f'/dev/{disk}'
    backup_ts = datetime.now().strftime('%Y%m%d-%H%M')
    backup_file = f'/var/tmp/backup_{disk}.{backup_ts}'
    call(f'sfdisk -d {device_path} > {backup_file}')
    print(f'Partition table backup saved to {backup_file}')


def list_partitions(disk: str):
    """List partition numbers of a given disk"""

    parts = set()
    part_num_expr = re.compile(disk + '([0-9]+)')
    with open('/proc/partitions') as partitions_file:
        for line in partitions_file:
            fields = line.strip().split()
            if len(fields) == 4 and fields[3] != 'name' and part_num_expr.match(fields[3]):
                part_idx = part_num_expr.match(fields[3]).group(1)
                parts.add(int(part_idx))
    return parts


def delete_partition(disk: str, partition_idx: int):
    cmd(f'parted /dev/{disk} rm {partition_idx}')


def format_disk_like(target: str, proto: str):
    cmd(f'sfdisk -d /dev/{proto} | sfdisk --force /dev/{target}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_argument_group()
    group.add_argument('-t', '--target', type=str, required=True, help='Target device to format')
    group.add_argument('-p', '--proto', type=str, required=True, help='Prototype device to use as reference')
    parser.add_argument('--by-id', action='store_true', help='Specify device by disk id')
    args = parser.parse_args()
    target = args.target
    proto = args.proto
    if args.by_id:
        target = device_from_id(target)
        proto = device_from_id(proto)

    target_disk = target
    eligible_target_disks = list_disks()

    proto_disk = proto
    eligible_proto_disks = eligible_target_disks.copy()
    eligible_proto_disks.remove(target_disk)

    if proto_disk == target_disk:
        print('The two disk drives must be different.')
        exit(1)

    if not os.path.exists(f'/dev/{proto_disk}'):
        print(f'Device /dev/{proto_disk} does not exist')
        exit(1)

    if not os.path.exists('/dev/' + target_disk):
        print(f'Device /dev/{target_disk} does not exist')
        exit(1)

    if target_disk not in eligible_target_disks:
        print(f'Device {target_disk} can not be formatted')
        exit(1)

    if proto_disk not in eligible_proto_disks:
        print(f'Device {proto_disk} can not be used as a prototype for {target_disk}')
        exit(1)

    if is_busy(target_disk):
        print(f'Disk device {target_disk} is busy, unable to format')
        exit(1)

    print(f'\nThis will re-format disk {target_disk} so that it has the same disk'
          f'\npartion sizes and offsets as {proto_disk}. This will not copy'
          f'\ndata from {proto_disk} to {target_disk}. But this will erase all'
          f'\ndata on {target_disk}.\n')

    if not ask_yes_no('Do you wish to proceed?'):
        print(f'Disk drive {target_disk} will not be re-formated')
        exit(0)

    print(f'Re-formating disk drive {target_disk}...')

    print('Making backup copy of partitions...')
    backup_partitions(target_disk)

    print('Deleting old partitions...')
    for p in list_partitions(target_disk):
        delete_partition(disk=target_disk, partition_idx=p)

    print(f'Creating new partitions on {target_disk} based on {proto_disk}...')
    format_disk_like(target=target_disk, proto=proto_disk)
    print('Done!')
