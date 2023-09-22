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

from vyos.utils.disk import device_from_id
from vyos.utils.process import cmd

def raid_sets():
    """
    Returns a list of RAID sets
    """
    with open('/proc/mdstat') as f:
        return [line.split()[0].rstrip(':') for line in f if line.startswith('md')]

def raid_set_members(raid_set_name: str):
    """
    Returns a list of members of a RAID set
    """
    with open('/proc/mdstat') as f:
        for line in f:
            if line.startswith(raid_set_name):
                return [l.split('[')[0] for l in line.split()[4:]]
    return []

def partitions():
    """
    Returns a list of partitions
    """
    with open('/proc/partitions') as f:
        p = [l.strip().split()[-1] for l in list(f) if l.strip()]
    p.remove('name')
    return p

def add_raid_member(raid_set_name: str, member: str, by_id: bool = False):
    """
    Add a member to an existing RAID set
    """
    if by_id:
        member = device_from_id(member)
    if raid_set_name not in raid_sets():
        raise ValueError(f"RAID set {raid_set_name} does not exist")
    if member not in partitions():
        raise ValueError(f"Partition {member} does not exist")
    if member in raid_set_members(raid_set_name):
        raise ValueError(f"Partition {member} is already a member of RAID set {raid_set_name}")
    cmd(f'mdadm --add /dev/{raid_set_name} /dev/{member}')
    disk = cmd(f'lsblk -ndo PKNAME /dev/{member}')
    cmd(f'grub-install /dev/{disk}')

def delete_raid_member(raid_set_name: str, member: str, by_id: bool = False):
    """
    Delete a member from an existing RAID set
    """
    if by_id:
        member = device_from_id(member)
    if raid_set_name not in raid_sets():
        raise ValueError(f"RAID set {raid_set_name} does not exist")
    if member not in raid_set_members(raid_set_name):
        raise ValueError(f"Partition {member} is not a member of RAID set {raid_set_name}")
    cmd(f'mdadm --remove /dev/{raid_set_name} /dev/{member}')
