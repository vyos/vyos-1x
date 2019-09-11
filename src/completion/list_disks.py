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

# Completion script used by show disks to collect physical disk

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-e", "--exclude", type=str, help="Exclude specified device from the result list")
args = parser.parse_args()

disks = set()
with open('/proc/partitions') as partitions_file:
    for line in partitions_file:
        fields = line.strip().split()
        if len(fields) == 4 and fields[3].isalpha() and fields[3] != 'name':
            disks.add(fields[3])

if args.exclude:
    disks.remove(args.exclude)

for disk in disks:
    print(disk)
