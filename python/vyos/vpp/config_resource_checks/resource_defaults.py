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
    # Default amount of buffers per NUMA (populated CPU socket)
    'buffers_per_numa': 16384,
    # Default size of buffer (in bytes)
    'data_size': 2048,
    # Default hugepage size for VPP
    'hugepage_size': '2M',
    # Default amount of memory allocated for VPP exclusive usage
    'main_heap_size': '3G',
    # Default main heap page size
    'main_heap_page_size': '2M',
    # Default size of buffers transferred via netlink
    'netlink_rx_buffer_size': 212992,
    # Default amount of memory allocated for VPP stats segment usage
    'statseg_heap_size': '128M',
    # Minimal amount of memory required to start VPP
    'min_memory': '8G',
    # Minimal number of physical CPU cores required to start VPP
    'min_cpus': 4,
    # Reserve at least 2 physical cores
    'reserved_cpu_cores': 2,
    # Default heap size for IPv6
    'ipv6_heap_size': '32M',
}
