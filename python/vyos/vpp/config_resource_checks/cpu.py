# Used for validating estimated CPU/physical cores use
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

from vyos.utils.cpu import get_available_cpus, get_core_count

from vyos.vpp.config_resource_checks.resource_defaults import default_resource_map


# Get default value for reserved cpu cores
reserved_cpus = default_resource_map.get('reserved_cpu_cores')


def available_cores_count(cpu_settings: dict) -> int:
    core_count = get_core_count()

    if cpu_settings.get('main_core'):
        core_count -= 1

    skip_cores = int(cpu_settings.get('skip_cores', 0))
    # The default settings assume that
    # at least 2 CPU cores should remain reserved for system use
    # (only in case of current runtime is not smoke test)
    if skip_cores < reserved_cpus:
        core_count -= reserved_cpus
    else:
        core_count -= skip_cores

    return core_count


def available_cores_list(skip_cores: int) -> list:
    # Available cores are all CPU cores without first N skipped cores that will not be used
    # Get all available physical cores - use set to filter out unique values
    cpu_cores = set(map(lambda el: el['cpu'], get_available_cpus()))
    cpu_cores = list(cpu_cores)

    return cpu_cores[skip_cores:]


def worker_cores_list(iface: str, worker_ranges: list) -> list:
    all_core_numbers = []
    for worker_range in worker_ranges:
        core_numbers = worker_range.split('-')

        if int(core_numbers[0]) > int(core_numbers[-1]):
            raise ValueError(
                f'Range for "{iface} workers {worker_range}" is not correct'
            )

        all_core_numbers.extend(range(int(core_numbers[0]), int(core_numbers[-1]) + 1))

    # Check for duplicates
    duplicates = set(
        [str(x) for n, x in enumerate(all_core_numbers) if x in all_core_numbers[:n]]
    )
    if duplicates:
        raise ValueError(
            f'Some workers in "{iface} workers" are duplicated: #{",".join(list(duplicates))}'
        )

    return all_core_numbers
