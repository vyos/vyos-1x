# Used for memory consumption calculations
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

import re

from vyos.utils.process import cmd
from vyos.vpp.utils import (
    human_memory_to_bytes,
    human_page_memory_to_bytes,
)
from vyos.vpp.config_resource_checks.resource_defaults import default_resource_map


def get_hugepages_info() -> dict:
    """
    Returns the information about HugePages for default hugepage size
    retrieved from /proc/meminfo
    """
    info = {}
    with open('/proc/meminfo', 'r') as meminfo:
        for line in meminfo:
            if line.startswith('Huge'):
                key, value, *_ = line.strip().split()
                info[key.rstrip(':')] = int(value)
    return info


def get_total_hugepages_memory() -> int:
    """
    Returns the total amount of hugepage memory (in bytes)
    """
    info = get_hugepages_info()
    hugepages_total = info.get('HugePages_Total')
    hugepage_size = info.get('Hugepagesize') * 1024

    return hugepage_size * hugepages_total


def get_numa_count():
    """
    Run `numactl --hardware` and parse the 'available:' line.
    """
    out = cmd('numactl --hardware')
    # e.g. "available: 2 nodes (0-1)"
    m = re.search(r'available:\s*(\d+)\s+nodes', out)
    return int(m.group(1)) if m else 0


def buffer_size(settings: dict) -> int:
    numa_count = get_numa_count()
    buffers_per_numa = int(
        settings.get('buffers', {}).get(
            'buffers_per_numa', default_resource_map.get('buffers_per_numa')
        )
    )
    data_size = int(
        settings.get('buffers', {}).get(
            'data_size', default_resource_map.get('data_size')
        )
    )
    buffers_memory = buffers_per_numa * data_size * numa_count
    return buffers_memory


def main_heap_page_size(settings: dict) -> int:
    heap_page_size = settings.get('memory', {}).get(
        'main_heap_page_size', default_resource_map.get('main_heap_page_size')
    )
    return human_page_memory_to_bytes(heap_page_size)


def memory_main_heap(settings: dict) -> int:
    heap_size = settings.get('memory', {}).get(
        'main_heap_size', default_resource_map.get('main_heap_size')
    )
    return human_memory_to_bytes(heap_size)


def ipv6_heap_size(settings: dict) -> int:
    heap_size = settings.get('ipv6', {}).get(
        'heap_size', default_resource_map.get('ipv6_heap_size')
    )
    return human_memory_to_bytes(heap_size)


def total_heap_size(heap_size: int, heap_page_size: int) -> int:
    return (heap_size + heap_page_size - 1) & ~(heap_page_size - 1)


def statseg_size(settings: dict) -> int:
    statseg_memory = settings.get('statseg', {}).get(
        'size', default_resource_map.get('statseg_heap_size')
    )
    return human_memory_to_bytes(statseg_memory)


def statseg_page_size(settings: dict) -> int:
    page_size = settings.get('statseg', {}).get('page_size', 'default')
    return human_page_memory_to_bytes(page_size)


def total_statseg_size(_statseg_size: int, _statseg_page: int) -> int:
    return (_statseg_size + _statseg_page - 1) & ~(_statseg_page - 1)


def total_memory_required(settings: dict) -> int:
    mem_required = 0

    mem_stats = {
        'memory_buffers': buffer_size(settings),
        'netlink_buffer_size': int(
            settings.get('lcp', {}).get(
                'rx_buffer_size', default_resource_map.get('netlink_rx_buffer_size')
            )
        ),
        'heap_size': total_heap_size(
            heap_size=memory_main_heap(settings),
            heap_page_size=main_heap_page_size(settings),
        ),
        'statseg_size': total_statseg_size(
            _statseg_size=statseg_size(settings),
            _statseg_page=statseg_page_size(settings),
        ),
        'ipv6_heap_size': ipv6_heap_size(settings),
    }

    for stat in mem_stats:
        mem_required += mem_stats[stat]

    return mem_required
