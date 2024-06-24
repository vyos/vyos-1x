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

def device_from_id(id):
    """ Return the device name from (partial) disk id """
    path = Path('/dev/disk/by-id')
    for device in path.iterdir():
        if device.name.endswith(id):
            return device.readlink().stem

def get_storage_stats(directory, human_units=True):
    """ Return basic storage stats for given directory """
    from re import sub as re_sub
    from vyos.utils.process import cmd
    from vyos.utils.convert import human_to_bytes

    # XXX: using `df -h` and converting human units to bytes
    # may seem pointless, but there's a reason.
    # df uses different header field names with `-h` and without it ("Size" vs "1K-blocks")
    # and outputs values in 1K blocks without `-h`,
    # so some amount of conversion is needed anyway.
    # Using `df -h` by default seems simpler.
    #
    # This is what the output looks like, as of Debian Buster/Bullseye:
    # $ df -h -t ext4 --output=source,size,used,avail,pcent
    # Filesystem      Size  Used Avail Use%
    # /dev/sda1        16G  7.6G  7.3G  51%

    out = cmd(f"df -h --output=source,size,used,avail,pcent {directory}")
    lines = out.splitlines()
    lists = [l.split() for l in lines]
    res = {lists[0][i]: lists[1][i] for i in range(len(lists[0]))}

    convert = (lambda x: x) if human_units else human_to_bytes

    stats = {}

    stats["filesystem"] = res["Filesystem"]
    stats["size"] = convert(res["Size"])
    stats["used"] = convert(res["Used"])
    stats["avail"] = convert(res["Avail"])
    stats["use_percentage"] = re_sub(r'%', '', res["Use%"])

    return stats

def get_persistent_storage_stats(human_units=True):
    from os.path import exists as path_exists

    persistence_dir = "/usr/lib/live/mount/persistence"
    if path_exists(persistence_dir):
        stats = get_storage_stats(persistence_dir, human_units=human_units)
    else:
        # If the persistence path doesn't exist,
        # the system is running from a live CD
        # and the concept of persistence storage stats is not applicable
        stats = None

    return stats
