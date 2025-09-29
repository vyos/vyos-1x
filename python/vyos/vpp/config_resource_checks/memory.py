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

import os
import re
import psutil

from vyos.utils.process import cmd
from vyos.vpp.utils import human_memory_to_bytes
from vyos.vpp.config_resource_checks.resource_defaults import default_resource_map


# VPP buffers default per NUMA node
MIN_BUFFERS = 16_384


def classify_page_size(page_size_bytes: int) -> str:
    """
    Returns one of: '4K', '2M', '1G' based on page size.
    """
    if page_size_bytes == 1 << 30:
        return '1G'
    if page_size_bytes == 2 << 20:
        return '2M'
    return '4K'


def get_hugepages_info() -> dict:
    """
    Returns the information about HugePages
    retrieved from /sys/kernel/mm/hugepages
    """
    base_path = '/sys/kernel/mm/hugepages'
    info = {}

    for entry in os.listdir(base_path):
        page_size_kb = entry[10:]
        page_size = human_memory_to_bytes(page_size_kb)
        key = classify_page_size(page_size)
        info[key] = {}

        with open(os.path.join(base_path, entry, 'nr_hugepages')) as f:
            count = int(f.read().strip())
            info[key]['pages'] = count
            info[key]['memory'] = page_size * count

    return info


def get_available_memory() -> dict:
    memory = {size: info.get('memory') for size, info in get_hugepages_info().items()}
    memory['4K'] = psutil.virtual_memory().available

    return memory


def get_vpp_used_memory() -> int:
    """
    Returns memory currently used by VPP in bytes (RSS value)
    """
    try:
        out = cmd('ps -o rss= -p $(pidof vpp)')
    except OSError:
        out = 0
    return int(out) << 10


def get_numa_count():
    """
    Run `numactl --hardware` and parse the 'available:' line.
    """
    out = cmd('numactl --hardware')
    # e.g. "available: 2 nodes (0-1)"
    m = re.search(r'available:\s*(\d+)\s+nodes', out)
    return int(m.group(1)) if m else 0


def buffer_page_size(settings: dict) -> int:
    page_size = settings.get('buffers', {}).get('page_size')
    return human_memory_to_bytes(page_size)


def buffer_size(settings: dict) -> int:
    numa_count = get_numa_count()
    buffers_per_numa = int(settings.get('buffers').get('buffers_per_numa'))
    data_size = int(settings.get('buffers').get('data_size'))
    buffers_memory = buffers_per_numa * data_size * numa_count
    return buffers_memory


def main_heap_page_size(settings: dict) -> int:
    heap_page_size = settings.get('memory').get('main_heap_page_size')
    return human_memory_to_bytes(heap_page_size)


def memory_main_heap(settings: dict) -> int:
    heap_size = settings.get('memory').get('main_heap_size')
    return human_memory_to_bytes(heap_size)


def ipv6_heap_size(settings: dict) -> int:
    heap_size = settings.get('ipv6').get('heap_size')
    return human_memory_to_bytes(heap_size)


def total_heap_size(heap_size: int, heap_page_size: int) -> int:
    return (heap_size + heap_page_size - 1) & ~(heap_page_size - 1)


def statseg_size(settings: dict) -> int:
    statseg_memory = settings.get('statseg').get('size')
    return human_memory_to_bytes(statseg_memory)


def statseg_page_size(settings: dict) -> int:
    page_size = settings.get('statseg').get('page_size')
    return human_memory_to_bytes(page_size)


def total_statseg_size(_statseg_size: int, _statseg_page: int) -> int:
    return (_statseg_size + _statseg_page - 1) & ~(_statseg_page - 1)


def total_memory_required(settings: dict) -> dict:
    memory = {'2M': 0, '1G': 0, '4K': 0}

    mem_stats = {
        'memory_buffers': (buffer_size(settings), buffer_page_size(settings)),
        'netlink_buffer_size': (
            int(
                settings.get('lcp', {})
                .get('netlink', {})
                .get(
                    'rx_buffer_size', default_resource_map.get('netlink_rx_buffer_size')
                )
            ),
            0,
        ),
        'heap_size': (
            total_heap_size(
                heap_size=memory_main_heap(settings),
                heap_page_size=main_heap_page_size(settings),
            ),
            main_heap_page_size(settings),
        ),
        'statseg_size': (
            total_statseg_size(
                _statseg_size=statseg_size(settings),
                _statseg_page=statseg_page_size(settings),
            ),
            statseg_page_size(settings),
        ),
        'ipv6_heap_size': (ipv6_heap_size(settings), 0),
    }

    for memory_size, page_size in mem_stats.values():
        memory[classify_page_size(page_size)] += memory_size

    return memory


def buffers_required(settings: dict, workers) -> int:
    """
    Calculate total VPP buffer requirements based on interface settings and workers.
    """
    buffers_total = 0
    for ifname, iface_config in settings.get('interface', {}).items():
        # Do not include XDP interfaces in buffer calculations.
        # Unlike DPDK, XDP does not use VPP-managed mbufs for RX/TX rings,
        # so buffer requirements cannot be derived from descriptors here.
        # Buffers for XDP are handled internally by the kernel/XDP layer,
        # not by VPP’s buffer allocator.
        if iface_config.get('driver') == 'xdp':
            continue
        dpdk_options = iface_config.get('dpdk_options', {})
        rx_queues = int(dpdk_options.get('num_rx_queues', 1))
        rx_desc = int(dpdk_options.get('num_rx_desc'))
        # default TX queues is equal to number of worker threads
        # plus 1 main thread
        tx_queues = int(dpdk_options.get('num_tx_queues', workers + 1))
        tx_desc = int(dpdk_options.get('num_tx_desc'))

        # buffers for RX/TX queues for interface
        buffers_total += rx_queues * rx_desc + tx_queues * tx_desc

    # per-thread buffer caches (approx. 256 buffers per worker)
    buffers_total += workers * 256

    # Safety margin for buffer calculations:
    # traffic bursts, alignment/metadata overhead etc.
    # The factor 2.5 is derived from VPP’s own calculations:
    # https://github.com/FDio/vpp/blob/stable/2506/extras/vpp_config/vpplib/AutoConfig.py#L609
    buffers_total = int(buffers_total * 2.5)

    # Enforce minimum required by VPP (16K buffers)
    return max(buffers_total, MIN_BUFFERS)
