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
from vyos.utils.cpu import get_core_count as total_core_count

from vyos.vpp.control_host import get_eth_driver
from vyos.vpp.config_resource_checks import cpu as cpu_checks, memory as mem_checks
from vyos.vpp.config_resource_checks.resource_defaults import default_resource_map
from vyos.vpp.utils import human_memory_to_bytes, bytes_to_human_memory


def verify_vpp_remove_kernel_interface(config: dict):
    """Common verify for removed kernel-interfaces.
    Verify that removed kernel interface are not used in 'vpp kernel-interfaces'.

    Example:
      delete vpp interfaces gre|vxlan <tag>X kernel-interface vpp-tunX
      set vpp kernel-interface vpp-tunX
    """
    if (
        'remove' in config
        and 'kernel_interface_removed' in config
        and 'vpp_kernel_interfaces' in config
    ):
        removed_interfaces = config['kernel_interface_removed']
        used_interfaces = config['vpp_kernel_interfaces']

        for interface in removed_interfaces:
            if interface in used_interfaces:
                raise ConfigError(
                    f'"{interface}" is still in use within "vpp kernel-interfaces". '
                    'Please remove it before proceeding.'
                )


def verify_vpp_change_kernel_interface(config: dict):
    """Common verify for changed kernel-interface

    Example:
      set vpp interfaces gre|vxlan <tag> kernel-interface vpp-tunX'
      commit
      set vpp interfaces gre|vxlan <tag> kernel-interface vpp-tunY'
      commit

    check if we have kernel interface config 'vpp kernel-interface vpp-tunX'
    """
    kernel_interface_removed = config.get('kernel_interface_removed', [])
    vpp_kernel_interfaces = config.get('vpp_kernel_interfaces', {})

    for interface in kernel_interface_removed:
        if interface in vpp_kernel_interfaces:
            raise ConfigError(
                f'interface "{interface}" is still in use within "vpp kernel-interfaces". '
                f'Please remove it "vpp kernel-interface {interface}" before proceeding.'
            )


def verify_vpp_exists_kernel_interface(config: dict):
    """Verify is a kernel-interface already created by another VPP LCP pair

    Example:
      set vpp interfaces vxlan vxlan10 kernel-interface vpp-tun10'
      commit
      set vpp interfaces vxlan vxlan20 kernel-interface vpp-tun10'
      commit
    """
    kernel_interface = config.get('kernel_interface', '')
    vpp_interface = config.get('ifname', '')
    candidate_kernel_interfaces = config.get('candidate_kernel_interfaces', [])

    for candidate_kernel_iface in candidate_kernel_interfaces:
        if (
            vpp_interface != candidate_kernel_iface[0]
            and kernel_interface == candidate_kernel_iface[1]
        ):
            raise ConfigError(
                f'Kernel interface "{kernel_interface}" is already configured for {candidate_kernel_iface[0]}. '
                'Duplicates are not allowed.'
            )


def verify_vpp_remove_xconnect_interface(config: dict):
    if not config.get('remove'):
        return
    for xconn_member, xconn_iface in config.get('xconn_members').items():
        if xconn_member == config.get('ifname'):
            raise ConfigError(
                f'interface "{xconn_member}" is still in use within "vpp interfaces xconnect". '
                f'Please remove it from "vpp interface xconnect {xconn_iface}" before proceeding.'
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


def verify_dev_driver(iface_name: str, driver_type: str) -> bool:
    # Lists of drivers compatible with DPDK and XDP
    drivers_dpdk: list[str] = [
        'atlantic',
        'bnx2x',
        'e1000',
        'ena',
        'gve',
        'hv_netvsc',
        'i40e',
        'ice',
        'igc',
        'ixgbe',
        'liquidio',
        'mlx4_core',
        'mlx5_core',
        'qede',
        'sfc',
        'tap',
        'tun',
        'virtio_net',
        'vmxnet3',
    ]

    drivers_xdp: list[str] = [
        'atlantic',
        'ena',
        'gve',
        'hv_netvsc',
        'i40e',
        'ice',
        'igb',
        'igc',
        'ixgbe',
        'mlx4_core',
        'mlx5_core',
        'qede',
        'sfc',
        'tap',
        'tun',
        'virtio_net',
        'vmxnet3',
    ]

    driver: str = get_eth_driver(iface_name)

    if driver_type == 'dpdk':
        if driver in drivers_dpdk:
            return True
    elif driver_type == 'xdp':
        if driver in drivers_xdp:
            return True
    else:
        raise ConfigError(f'"Driver type {driver_type} is wrong')

    return False


def verify_vpp_minimum_cpus():
    """
    Verify that the host system has enough physical CPU cores
    Current minimal requirement is 4
    """
    min_cpus = default_resource_map.get('min_cpus')
    if total_core_count() < min_cpus:
        raise ConfigError(
            'This system does not meet minimal requirements for VPP. '
            f'Minimum {min_cpus} CPU cores are required.'
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


def verify_vpp_settings_cpu_skip_cores(skip_cores: int):
    cpu_cores = total_core_count()

    # The number of skipped cores must not be greater than
    # available CPU cores in the system - 1 for main thread
    if skip_cores > (cpu_cores - 1):
        raise ConfigError(
            f'The system does not have enough available CPUs to skip '
            f'(reduce "cpu skip-cores" to {cpu_cores} or less)'
        )


def verify_vpp_settings_cpu_and_corelist_workers(settings: dict):
    """
    `set vpp settings cpu workers` and `set vpp settings cpu corelist-workers`
    are mutually exclusive!
    """
    if (
        'corelist_workers' in settings or 'workers' in settings
    ) and 'main_core' not in settings:
        raise ConfigError('"cpu main-core" is required but not set!')

    if 'corelist_workers' in settings and 'workers' in settings:
        raise ConfigError(
            '"cpu corelist-workers" and "cpu workers" cannot be used at the same time!'
        )


def verify_vpp_cpu_main_core(cpu_settings: dict) -> None:
    """Check that the main core is available"""
    skip_cores = int(cpu_settings.get('skip_cores', 0))
    available_cores = cpu_checks.available_cores_list(skip_cores)
    main_core = int(cpu_settings['main_core'])

    if main_core not in available_cores:
        raise ConfigError(
            'Cannot set main core for VPP process: '
            f'CPU#{main_core} is not available.'
        )


def verify_vpp_settings_cpu_workers(cpu_settings: dict):
    """
    Verify that the system has enough available CPU cores
    to run a given amount of worker processes (1 worker/core)
    """
    workers = int(cpu_settings.get('workers', 0))
    available_cores = cpu_checks.available_cores_count(cpu_settings)

    if workers > available_cores:
        raise ConfigError(
            f'Not enough free CPU cores for {workers} VPP workers '
            f'(reduce to {available_cores} or less)'
        )


def verify_vpp_settings_cpu_corelist_workers(cpu_settings: dict):
    """
    Verify that the CPU cores provided to the config are free and can be used by VPP
    """
    workers = cpu_settings.get('corelist_workers')
    main_core = int(cpu_settings.get('main_core'))
    skip_cores = int(cpu_settings.get('skip_cores', 0))
    available_cores = cpu_checks.available_cores_list(skip_cores)
    try:
        all_core_nums = cpu_checks.worker_cores_list(
            iface='cpu corelist', worker_ranges=workers
        )
    except ValueError as e:
        raise ConfigError(str(e))

    error_msg = 'Cannot set VPP "cpu corelist-workers"'

    if main_core in all_core_nums:
        raise ConfigError(
            f'CPU#{main_core} is set as main core and should not '
            'be included to the corelist-workers'
        )

    invalid_cores = [str(el) for el in all_core_nums if el not in available_cores]
    if invalid_cores:
        raise ConfigError(
            f'{error_msg}: CPU# {",".join(invalid_cores)} are not available.'
        )

    if len(all_core_nums) > cpu_checks.available_cores_count(cpu_settings):
        raise ConfigError(f'{error_msg}: Not enough free CPUs in the system.')


def verify_vpp_nat44_workers(workers: int, nat44_workers: list):
    if workers < 1:
        raise ConfigError(
            '"nat44 workers" requires cpu workers or corelist-workers to be set!'
        )
    try:
        nat_workers = cpu_checks.worker_cores_list(
            iface='nat44', worker_ranges=nat44_workers
        )
    except ValueError as e:
        raise ConfigError(str(e))

    invalid_workers = [str(el) for el in nat_workers if el not in range(workers)]
    if invalid_workers:
        raise ConfigError(
            f'Cannot set VPP "nat44 workers": worker(s) #{",".join(invalid_workers)} not available. '
            f'Available worker ids: {",".join(map(str, range(workers)))}'
        )


def verify_vpp_statseg_size(settings: dict):
    statseg_size = mem_checks.statseg_size(settings)

    if 'size' in settings.get('statseg'):
        if statseg_size < 128 << 20:
            raise ConfigError('The statseg size must be greater than or equal to 128M')

    if 'page_size' in settings['statseg']:
        statseg_page_size = mem_checks.statseg_page_size(settings)
        if statseg_page_size > statseg_size:
            readable_statseg_page = bytes_to_human_memory(statseg_page_size, 'K')
            raise ConfigError(
                f'The statseg size must be greater than or equal to page-size ({readable_statseg_page})'
            )


def verify_vpp_interfaces_dpdk_num_queues(qtype: str, num_queues: int, workers: int):
    """
    Verify that VPP has enough workers to run the given amount of RX/TX queues
    1 queue per 1 worker is assumed as default
    """

    if num_queues > workers:
        raise ConfigError(
            f'The number of {qtype} queues cannot be greater than the number of configured VPP workers: '
            f'workers: {workers}, queues: {num_queues}'
        )


def verify_routes_count(settings: dict, workers: int):
    """
    Maximum routes count depending on main heap size,
    statistics segment size and workers
    """
    counters = 2  # 2 counters for each route
    bytes = 16  # each counter consumes 16 bytes
    statseg_scale = 2
    statseg_size = settings['statseg']['size']
    statseg_size_in_bytes = human_memory_to_bytes(statseg_size)
    main_heap = settings['memory']['main_heap_size']
    main_heap_in_gb = human_memory_to_bytes(main_heap) >> 30

    formula = (workers + 1) * counters * bytes * statseg_scale
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


def verify_vpp_buffers(settings: dict, workers: int):
    buffers_configured = int(settings['buffers']['buffers_per_numa'])

    buffers_required = mem_checks.buffers_required(settings, workers)

    if buffers_required > buffers_configured:
        raise ConfigError(
            'Not enough buffers to initialize RX/TX queues for interfaces. '
            f'Set "vpp settings buffers buffers-per-numa" to {buffers_required} or higher'
        )
