#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
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
import sys
from datetime import datetime
from time import sleep

from vyos.util import is_admin, ask_yes_no
from vyos.command import call
from vyos.command import cmd
from vyos.util import DEVNULL

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
    return call(f'sudo blockdev --rereadpt /dev/{disk}', stderr=DEVNULL) != 0


def backup_partitions(disk: str):
    """Save sfdisk partitions output to a backup file"""

    device_path = '/dev/' + disk
    backup_ts = datetime.now().strftime('%Y-%m-%d-%H:%M')
    backup_file = '/var/tmp/backup_{}.{}'.format(disk, backup_ts)
    cmd(f'sudo /sbin/sfdisk -d {device_path} > {backup_file}')


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
    cmd(f'sudo /sbin/parted /dev/{disk} rm {partition_idx}')


def format_disk_like(target: str, proto: str):
    cmd(f'sudo /sbin/sfdisk -d /dev/{proto} | sudo /sbin/sfdisk --force /dev/{target}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_argument_group()
    group.add_argument('-t', '--target', type=str, required=True, help='Target device to format')
    group.add_argument('-p', '--proto', type=str, required=True, help='Prototype device to use as reference')
    args = parser.parse_args()

    if not is_admin():
        print('Must be admin or root to format disk')
        sys.exit(1)

    target_disk = args.target
    eligible_target_disks = list_disks()

    proto_disk = args.proto
    eligible_proto_disks = eligible_target_disks.copy()
    eligible_proto_disks.remove(target_disk)

    fmt = {
        'target_disk': target_disk,
        'proto_disk': proto_disk,
    }

    if proto_disk == target_disk:
        print('The two disk drives must be different.')
        sys.exit(1)

    if not os.path.exists('/dev/' + proto_disk):
        print('Device /dev/{proto_disk} does not exist'.format_map(fmt))
        sys.exit(1)

    if not os.path.exists('/dev/' + target_disk):
        print('Device /dev/{target_disk} does not exist'.format_map(fmt))
        sys.exit(1)

    if target_disk not in eligible_target_disks:
        print('Device {target_disk} can not be formatted'.format_map(fmt))
        sys.exit(1)

    if proto_disk not in eligible_proto_disks:
        print('Device {proto_disk} can not be used as a prototype for {target_disk}'.format_map(fmt))
        sys.exit(1)

    if is_busy(target_disk):
        print("Disk device {target_disk} is busy. Can't format it now".format_map(fmt))
        sys.exit(1)

    print('This will re-format disk {target_disk} so that it has the same disk\n'
          'partion sizes and offsets as {proto_disk}. This will not copy\n'
          'data from {proto_disk} to {target_disk}. But this will erase all\n'
          'data on {target_disk}.\n'.format_map(fmt))

    if not ask_yes_no("Do you wish to proceed?"):
        print('OK. Disk drive {target_disk} will not be re-formated'.format_map(fmt))
        sys.exit(0)

    print('OK. Re-formating disk drive {target_disk}...'.format_map(fmt))

    print('Making backup copy of partitions...')
    backup_partitions(target_disk)
    sleep(1)

    print('Deleting old partitions...')
    for p in list_partitions(target_disk):
        delete_partition(disk=target_disk, partition_idx=p)

    print('Creating new partitions on {target_disk} based on {proto_disk}...'.format_map(fmt))
    format_disk_like(target=target_disk, proto=proto_disk)
    print('Done.')
