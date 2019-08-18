#!/bin/bash
#
# Module: vyos-show-ram.sh
# Displays memory usage information in minimalistic format
#
# Copyright (C) 2019 VyOS maintainers and contributors
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

MB_DIVISOR=1024

TOTAL=$(cat /proc/meminfo | grep -E "^MemTotal:" | awk -F ' ' '{print $2}')
FREE=$(cat /proc/meminfo | grep -E "^MemFree:" | awk -F ' ' '{print $2}')
BUFFERS=$(cat /proc/meminfo | grep -E "^Buffers:" | awk -F ' ' '{print $2}')
CACHED=$(cat /proc/meminfo | grep -E "^Cached:" | awk -F ' ' '{print $2}')

DISPLAY_FREE=$(( ($FREE + $BUFFERS + $CACHED) / $MB_DIVISOR ))
DISPLAY_TOTAL=$(( $TOTAL / $MB_DIVISOR ))
DISPLAY_USED=$(( $DISPLAY_TOTAL - $DISPLAY_FREE ))

echo "Total: $DISPLAY_TOTAL"
echo "Free:  $DISPLAY_FREE"
echo "Used:  $DISPLAY_USED"
