# Copyright 2022 VyOS maintainers and contributors <maintainers@vyos.io>
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

from json import loads as json_loads
from os import sync

from psutil import disk_partitions

from vyos.util import run, cmd


def disk_cleanup(drive_path: str) -> None:
    """Clean up disk partition table (MBR and GPT)
    Zeroize primary and secondary headers - first and last 17408 bytes
    (512 bytes * 34 LBA) on a drive

    Args:
        drive_path (str): path to a drive that needs to be cleaned
    """
    run(f'sgdisk -Z {drive_path}')


def find_persistence() -> str:
    """Find a mountpoint for persistence storage

    Returns:
        str: Path where 'persistance' pertition is mounted, Empty if not found
    """
    mounted_partitions = disk_partitions()
    for partition in mounted_partitions:
        if partition.mountpoint.endswith('/persistence'):
            return partition.mountpoint
    return ''


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
