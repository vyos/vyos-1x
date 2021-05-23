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

# Completion script used by show disks to collect physical disk

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-e", "--exclude", type=str, help="Exclude specified device from the result list")
args = parser.parse_args()

disks = set()
with open('/proc/partitions') as f:
  table = f.read()

for line in table.splitlines()[1:]:
    fields = line.strip().split()
    # probably an empty line at the top
    if len(fields) == 0:
        continue
    disks.add(fields[3])

if 'loop0' in disks:
    disks.remove('loop0')
if 'sr0' in disks:
    disks.remove('sr0')

if args.exclude:
    disks.remove(args.exclude)

for disk in disks:
    print(disk)
