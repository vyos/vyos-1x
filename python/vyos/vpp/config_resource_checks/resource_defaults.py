# Default values for resource consumption checks
#
# Copyright (C) VyOS Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


default_resource_map = {
    # Default size of buffers transferred via netlink
    'netlink_rx_buffer_size': 212992,
    # Minimal amount of memory required to start VPP
    'min_memory': '8G',
    # Minimal number of physical CPU cores required to start VPP
    'min_cpus': 4,
    # Reserve at least 2 physical cores
    'reserved_cpu_cores': 2,
}
