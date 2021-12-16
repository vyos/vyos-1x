#!/usr/bin/env bash
#
# Copyright (C) 2021 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# ROOT_PART_DEV – root partition device path
# ROOT_PART_NAME – root partition device name
# ROOT_DEV_NAME – disk device name
# ROOT_DEV – disk device path
# ROOT_PART_NUM – number of root partition on disk
# ROOT_DEV_SIZE – disk total size in 512 bytes sectors
# ROOT_PART_SIZE – root partition total size in 512 bytes sectors
# ROOT_PART_START – number of 512 bytes sector where root partition starts
# AVAILABLE_EXTENSION_SIZE – calculation available disk space after root partition in 512 bytes sectors
ROOT_PART_DEV=$(findmnt /usr/lib/live/mount/persistence -o source -n)
ROOT_PART_NAME=$(echo "$ROOT_PART_DEV" | cut -d "/" -f 3)
ROOT_DEV_NAME=$(echo /sys/block/*/"${ROOT_PART_NAME}" | cut -d "/" -f 4)
ROOT_DEV="/dev/${ROOT_DEV_NAME}"
ROOT_PART_NUM=$(cat "/sys/block/${ROOT_DEV_NAME}/${ROOT_PART_NAME}/partition")
ROOT_DEV_SIZE=$(cat "/sys/block/${ROOT_DEV_NAME}/size")
ROOT_PART_SIZE=$(cat "/sys/block/${ROOT_DEV_NAME}/${ROOT_PART_NAME}/size")
ROOT_PART_START=$(cat "/sys/block/${ROOT_DEV_NAME}/${ROOT_PART_NAME}/start")
AVAILABLE_EXTENSION_SIZE=$((ROOT_DEV_SIZE - ROOT_PART_START - ROOT_PART_SIZE - 8))

#
# Check if device have space for root partition growing up.
#
if [ $AVAILABLE_EXTENSION_SIZE -lt 1 ]; then
    echo "There is no available space for root partition extension"
    exit 0;
fi

#
# Resize the partition and grow the filesystem.
#
# "print" and "Fix" directives were added to fix GPT table if it corrupted after virtual drive extension.
# If GPT table is corrupted we'll get Fix/Ignore dialogue after "print" command.
# "Fix" will be the answer for this dialogue. 
# If GPT table is fine and no auto-fix dialogue appeared the directive "Fix" simply will print parted utility help info.  
parted -m ${ROOT_DEV} ---pretend-input-tty > /dev/null 2>&1 <<EOF 
print
Fix
resizepart
${ROOT_PART_NUM}
Yes
100%
EOF
partprobe > /dev/null 2>&1
resize2fs ${ROOT_PART_DEV} > /dev/null 2>&1
