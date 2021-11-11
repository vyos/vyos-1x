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

#
# Function to get the vyos version from the commandline.
#
get_version () {
for item in `cat /proc/cmdline`; do
  if [  "vyos-union" == "${item%=*}" ]; then
    echo ${item#*=}
  fi
done
}

#
# VERSION is the output of the get_version output.
# DEVICEPART is the device partition where VyOS is mounted on.
# DEVICEPATH is the path to the device where VyOS is mounted on.
# DEVICE is the device of the device partition.
# PARTNR is the device partition number used for parted.
#
VERSION=$(get_version)
DEVICEPART=$(mount | grep $VERSION/grub | cut -d' ' -f1 | rev | cut -d'/' -f1 | rev)
DEVICEPATH=$(mount | grep $VERSION/grub | cut -d' ' -f1 | rev | cut -d'/' -f2- | rev)
DEVICE=$(lsblk -no pkname $DEVICEPATH/$DEVICEPART)
PARTNR=$(grep -c $DEVICEPART /proc/partitions)

#
# Check if the device really exits.
#
fdisk -l $DEVICEPATH/$DEVICE >> /dev/null 2>&1 || (echo "could not find device $DEVICE" && exit 1)

#
# START is the partition starting sector.
# CURSIZE is the partition start sector + the partition end sector.
# MAXSIZE is the device end sector.
#
START=$(cat /sys/block/$DEVICE/$DEVICEPART/start)
CURSIZE=$(($START+$(cat /sys/block/$DEVICE/$DEVICEPART/size)))
MAXSIZE=$(($(cat /sys/block/$DEVICE/size)-8))

#
# Check if the device size is larger then the partition size
# and if that is the case, resize the partition and grow the filesystem.
#
if [ $MAXSIZE -gt $CURSIZE ]; then
parted "${DEVICEPATH}/${DEVICE}" ---pretend-input-tty > /dev/null 2>&1 <<EOF
unit
s
resizepart
${PARTNR}
Yes
"$MAXSIZE"
quit
EOF
  partprobe > /dev/null 2>&1
  resize2fs ${DEVICEPATH}/$DEVICEPART > /dev/null 2>&1
fi

