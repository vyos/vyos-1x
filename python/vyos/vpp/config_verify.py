# Used for verifying configuration vpp interfaces
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

import psutil

from vyos import ConfigError
from vyos.base import Warning
from vyos.utils.cpu import get_core_count as total_core_count, get_cpus

from vyos.vpp.config_resource_checks import memory as mem_checks
from vyos.vpp.config_resource_checks.resource_defaults import default_resource_map
from vyos.vpp.utils import human_memory_to_bytes, bytes_to_human_memory


def verify_vpp_remove_xconnect_interface(config: dict):
    if not 'deleted' in config:
        return
    for xconn_member, xconn_iface in config.get('xconn_members').items():
        if xconn_member == config.get('ifname'):
            raise ConfigError(
                f'interface "{xconn_member}" is still in use within "interfaces vpp xconnect". '
                f'Please remove it from "interfaces vpp xconnect {xconn_iface}" before proceeding.'
            )


def verify_vpp_remove_bridge_interface(config: dict):
    if not 'deleted' in config:
        return
    for bridge_member, bridge_iface in config.get('bridge_members').items():
        if bridge_member == config.get('ifname'):
            raise ConfigError(
                f'interface "{bridge_member}" is still in use within "interfaces vpp bridge". '
                f'Please remove it from "interfaces vpp bridge {bridge_iface}" before proceeding.'
            )


def verify_vpp_tunnel_source_address(config: dict):
    from vyos.utils.network import is_intf_addr_assigned

    address = config.get('source_address')
    for iface in config.get('vpp_ether_vif_ifaces', []):
        if is_intf_addr_assigned(iface, address):
            return True

    raise ConfigError(
        f'Source address "{address}" is not assigned on any Ethernet or VIF interface!'
    )


def create_cpu_error_message(cpus_required: int, cpus_available: int = None) -> str:
    cpu_info = get_cpus()
    logical_cores = sum(
        [int(s.get('siblings')) if 'siblings' in s else 1 for s in cpu_info]
    )

    reserved_cpus = default_resource_map.get('reserved_cpu_cores')

    available_str = (
        (
            '---'.ljust(72)
            + 'Reserved:'.ljust(72)
            + f'For system: {reserved_cpus}'.ljust(72)
            + f'VPP main thread: 1'.ljust(72)
            + '---'.ljust(72)
            + 'Available:'.ljust(72)
            + f'Physical cores: {max(cpus_available, 0)}'
        )
        if cpus_available is not None
        else ''
    )

    message = (
        '---'.ljust(72)
        + 'Total in the system:'.ljust(72)
        + f'Physical cores: {total_core_count()}'.ljust(72)
        + f'Logical cores: {logical_cores}'.ljust(72)
        + '---'.ljust(72)
        + 'Required:'.ljust(72)
        + f'Physical cores: {cpus_required}'.ljust(72)
        + available_str
    )

    return message


def verify_vpp_minimum_cpus():
    """
    Verify that the host system has enough physical CPU cores
    Current minimal requirement is 4
    """
    min_cpus = default_resource_map.get('min_cpus')
    if total_core_count() < min_cpus:
        raise ConfigError(
            'This system does not meet minimal requirements for VPP. '.ljust(72)
            + create_cpu_error_message(min_cpus)
        )


def verify_vpp_minimum_memory():
    """
    Verify that the host system has enough RAM
    Calculate by retrieving the amount of physical memory
    And the minimal requirement (currently 8 GB). Round before comparing -
    To avoid situations like when a machine nominally has 8192 MB (8 giga/gibibytes)
    But the OS sees only 7.75 GB, creating a fail condition for this check
    """
    min_mem = default_resource_map.get('min_memory')
    total_memory = round(psutil.virtual_memory().total / (1024**3))
    min_memory = round(human_memory_to_bytes(min_mem) / (1024**3))

    if total_memory < min_memory:
        raise ConfigError(
            'This system does not meet minimal requirements for VPP. '
            f'Minimum {min_memory} GB of RAM are required.'
        )


def verify_vpp_main_heap_size(settings: dict):
    main_heap_size = mem_checks.memory_main_heap(settings)
    main_heap_page_size = mem_checks.main_heap_page_size(settings)

    if main_heap_size < 1 << 30:
        raise ConfigError('The main heap size must be greater than or equal to 1G')

    readable_heap_page = bytes_to_human_memory(main_heap_page_size, 'K')

    if main_heap_page_size > main_heap_size:
        raise ConfigError(
            f'The main heap size must be greater than or equal to page-size ({readable_heap_page})'
        )


def verify_vpp_memory(config: dict):
    memory_required = mem_checks.total_memory_required(config['settings'])
    memory_available = mem_checks.get_available_memory()

    # Check if there is a config currently active
    # If yes, calculate how much memory it consumes (only for 4k pages)
    # and exclude it from required memory
    if config.get('effective'):
        memory_effective = mem_checks.total_memory_required(
            config['effective']['settings']
        )

        # If we want to reduce memory configs then we don't need
        # to check 4K memory type
        if memory_effective['4K'] >= memory_required['4K']:
            del memory_required['4K']
        else:
            # Get memory currently used by VPP and add it to available memory
            memory_used = mem_checks.get_vpp_used_memory()
            memory_available['4K'] += memory_used

    memory_required_gb = {k: round(v / 1024**3, 1) for k, v in memory_required.items()}
    memory_available_gb = {
        k: round(v / 1024**3, 1) for k, v in memory_available.items()
    }

    errors = {}
    for page_size, req_gb in memory_required_gb.items():
        avail_gb = memory_available_gb.get(page_size, 0)

        if req_gb > avail_gb:
            label = 'System' if page_size == '4K' else f'{page_size} HugePages'
            errors[page_size] = (
                f'{label} memory: available {avail_gb} GB, '
                f'required {memory_required_gb[page_size]} GB'
            )

    if errors:
        raise ConfigError(
            'Not enough free memory to start VPP! '.ljust(72)
            + '. '.join([line.ljust(72) for line in errors.values()])
            + (
                'To add HugePages memory please use command '.ljust(72)
                + '"set system option kernel memory hugepage-size ..." and reboot!'
                if any(k in errors for k in ('2M', '1G'))
                else ''
            )
        )


def verify_vpp_cpu_cores(cpu_cores: int):
    """
    Verify that the system has enough available CPU cores
    to run a given amount of worker processes (1 worker/core)
    """
    total_cores = total_core_count()
    reserved_cpus = default_resource_map.get('reserved_cpu_cores')
    available_cores = total_cores - reserved_cpus

    if cpu_cores > available_cores:
        raise ConfigError(
            f'Not enough free physical CPU cores for {cpu_cores} "cpu-cores" '.ljust(72)
            + create_cpu_error_message(cpu_cores, available_cores)
        )


def verify_vpp_statseg_size(settings: dict):
    statseg_size = mem_checks.statseg_size(settings)

    if 'size' in settings['resource_allocation']['memory']['stats']:
        if statseg_size < 128 << 20:
            raise ConfigError('The "stats size" must be greater than or equal to 128M')

    if 'page_size' in settings['resource_allocation']['memory']['stats']:
        statseg_page_size = mem_checks.statseg_page_size(settings)
        if statseg_page_size > statseg_size:
            readable_statseg_page = bytes_to_human_memory(statseg_page_size, 'K')
            raise ConfigError(
                f'The "stats size" must be greater than or equal to page-size ({readable_statseg_page})'
            )


def verify_vpp_interfaces_dpdk_num_queues(qtype: str, num_queues: int, workers: int):
    """
    Verify that VPP has enough workers to run the given amount of RX/TX queues
    1 queue per 1 worker is assumed as default
    """

    if num_queues > workers:
        raise ConfigError(
            f'The number of {qtype} queues cannot be greater than the number of configured VPP "cpu-cores": '
            f'cpu-cores: {workers}, queues: {num_queues}'
        )


def verify_routes_count(settings: dict):
    """
    Maximum routes count depending on main heap size,
    statistics segment size and workers
    """
    counters = 2  # 2 counters for each route
    bytes = 16  # each counter consumes 16 bytes
    statseg_scale = 2
    cpu_cores = int(settings['resource_allocation']['cpu_cores'])
    statseg_size = settings['resource_allocation']['memory']['stats']['size']
    statseg_size_in_bytes = human_memory_to_bytes(statseg_size)
    main_heap = settings['resource_allocation']['memory']['main_heap_size']
    main_heap_in_gb = human_memory_to_bytes(main_heap) >> 30

    formula = cpu_cores * counters * bytes * statseg_scale
    routes_count_statseg = statseg_size_in_bytes / formula
    routes_count_statseg = round(routes_count_statseg / 1_000_000, 2)
    routes_count_mh = main_heap_in_gb * 2
    routes_count_min = min(routes_count_statseg, routes_count_mh)
    Warning(
        f'NOTE: Current dataplane capacity (estimated): {routes_count_min} M IPv4 routes. '
        'Exceeding these values will lead to a dataplane out-of-memory condition and a crash. '
        'Extensive use of features like ACLs, NAT and others may reduce the numbers above. '
        'Please read the documentation for details: https://docs.vyos.io/'
    )


def verify_vpp_buffers(settings: dict):
    buffers_configured = int(
        settings['resource_allocation']['buffers']['buffers_per_numa']
    )

    buffers_required = mem_checks.buffers_required(settings)

    if buffers_required > buffers_configured:
        raise ConfigError(
            'Not enough buffers to initialize RX/TX queues for interfaces. '
            f'Set "vpp settings resource-allocation buffers buffers-per-numa" to {buffers_required} or higher'
        )


def verify_nat_interfaces(config: dict, feature_name: str):
    """
    Verify that interfaces are not already used in the selected NAT feature.
    Example:
        verify_nat_interfaces(config, 'nat44')
        verify_nat_interfaces(config, 'cgnat')
    """
    directions = ['inside', 'outside']
    interfaces = config.get('interface', {})
    nat_interfaces = config.get(f'{feature_name}_config', {}).get('interface', {})

    for direction in directions:
        for iface in interfaces.get(direction, []):
            # Check if iface is used in any nat44/cgnat direction
            nat_dir = next(
                (d for d in directions if iface in nat_interfaces.get(d, [])), None
            )
            if nat_dir:
                raise ConfigError(
                    f'Cannot use {iface} as {direction} interface: '
                    f'it is already configured as {nat_dir} interface in {feature_name.upper()}'
                )
