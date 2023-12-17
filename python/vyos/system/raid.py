# Copyright 2023 VyOS maintainers and contributors <maintainers@vyos.io>
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

"""RAID related functions"""

from pathlib import Path
from shutil import copy
from dataclasses import dataclass

from vyos.utils.process import cmd, run
from vyos.system import disk


@dataclass
class RaidDetails:
    """RAID type"""
    name: str
    level: str
    members: list[str]
    disks: list[disk.DiskDetails]


def raid_create(raid_members: list[str],
                raid_name: str = 'md0',
                raid_level: str = 'raid1') -> None:
    """Create a RAID array

    Args:
        raid_name (str): a name of array (data, backup, test, etc.)
        raid_members (list[str]): a list of array members
        raid_level (str, optional): an array level. Defaults to 'raid1'.
    """
    raid_devices_num: int = len(raid_members)
    raid_members_str: str = ' '.join(raid_members)
    for part in raid_members:
        drive: str = disk.partition_parent(part)
        # set partition type GUID for raid member; cf.
        # https://en.wikipedia.org/wiki/GUID_Partition_Table#Partition_type_GUIDs
        command: str = f'sgdisk --typecode=3:A19D880F-05FC-4D3B-A006-743F0F84911E {drive}'
        cmd(command)
    command: str = f'mdadm --create /dev/{raid_name} -R --metadata=1.0 \
        --raid-devices={raid_devices_num} --level={raid_level} \
        {raid_members_str}'

    cmd(command)

    raid = RaidDetails(
        name = f'/dev/{raid_name}',
        level = raid_level,
        members = raid_members,
        disks = [disk.from_partition(m) for m in raid_members]
    )

    return raid

def clear():
    """Deactivate all RAID arrays"""
    command: str = 'mdadm --examine --scan'
    raid_config = cmd(command)
    if not raid_config:
        return
    command: str = 'mdadm --run /dev/md?*'
    run(command)
    command: str = 'mdadm --assemble --scan --auto=yes --symlink=no'
    run(command)
    command: str = 'mdadm --stop --scan'
    run(command)


def update_initramfs() -> None:
    """Update initramfs"""
    mdadm_script = '/etc/initramfs-tools/scripts/local-top/mdadm'
    copy('/usr/share/initramfs-tools/scripts/local-block/mdadm', mdadm_script)
    p = Path(mdadm_script)
    p.write_text(p.read_text().replace('$((COUNT + 1))', '20'))
    command: str = 'update-initramfs -u'
    cmd(command)

def update_default(target_dir: str) -> None:
    """Update /etc/default/mdadm to start MD monitoring daemon at boot
    """
    source_mdadm_config = '/etc/default/mdadm'
    target_mdadm_config = Path(target_dir).joinpath('/etc/default/mdadm')
    target_mdadm_config_dir = Path(target_mdadm_config).parent
    Path.mkdir(target_mdadm_config_dir, parents=True, exist_ok=True)
    s = Path(source_mdadm_config).read_text().replace('START_DAEMON=false',
                                                      'START_DAEMON=true')
    Path(target_mdadm_config).write_text(s)

def get_uuid(device: str) -> str:
    """Get UUID of a device"""
    command: str = f'tune2fs -l {device}'
    l = cmd(command).splitlines()
    uuid = next((x for x in l if x.startswith('Filesystem UUID')), '')
    return uuid.split(':')[1].strip() if uuid else ''

def get_uuids(raid_details: RaidDetails) -> tuple[str]:
    """Get UUIDs of RAID members

    Args:
        raid_name (str): a name of array (data, backup, test, etc.)

    Returns:
        tuple[str]: root_disk uuid, root_md uuid
    """
    raid_name: str = raid_details.name
    root_partition: str = raid_details.members[0]
    uuid_root_disk: str = get_uuid(root_partition)
    uuid_root_md: str = get_uuid(raid_name)
    return uuid_root_disk, uuid_root_md
