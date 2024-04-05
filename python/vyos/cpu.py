# Copyright (C) 2022-2024 VyOS maintainers and contributors
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

"""
Retrieves (or at least attempts to retrieve) the total number of real CPU cores
installed in a Linux system.

The issue of core count is complicated by existence of SMT, e.g. Intel's Hyper Threading.
GNU nproc returns the number of LOGICAL cores,
which is 2x of the real cores if SMT is enabled.

The idea is to find all physical CPUs and add up their core counts.
It has special cases for x86_64 and MAY work correctly on other architectures,
but nothing is certain.
"""

import re


def _read_cpuinfo():
    with open('/proc/cpuinfo', 'r') as f:
        lines = f.read().strip()
        return re.split(r'\n+', lines)

def _split_line(l):
    l = l.strip()
    parts = re.split(r'\s*:\s*', l)
    return (parts[0], ":".join(parts[1:]))

def _find_cpus(cpuinfo_lines):
    # Make a dict because it's more convenient to work with later,
    # when we need to find physicall distinct CPUs there.
    cpus = {}

    cpu_number = 0

    for l in cpuinfo_lines:
        key, value = _split_line(l)
        if key == 'processor':
            cpu_number = value
            cpus[cpu_number] = {}
        else:
            cpus[cpu_number][key] = value

    return cpus

def _find_physical_cpus():
    cpus = _find_cpus(_read_cpuinfo())

    phys_cpus = {}

    for num in cpus:
        if 'physical id' in cpus[num]:
            # On at least some architectures, CPUs in different sockets
            # have different 'physical id' field, e.g. on x86_64.
            phys_id = cpus[num]['physical id']
            if phys_id not in phys_cpus:
                phys_cpus[phys_id] = cpus[num]
        else:
            # On other architectures, e.g. on ARM, there's no such field.
            # We just assume they are different CPUs,
            # whether single core ones or cores of physical CPUs.
            phys_cpus[num] = cpus[num]

    return phys_cpus

def get_cpus():
    """ Returns a list of /proc/cpuinfo entries that belong to different CPUs.
    """
    cpus_dict = _find_physical_cpus()
    return list(cpus_dict.values())

def get_core_count():
    """ Returns the total number of physical CPU cores
        (even if Hyper-Threading or another SMT is enabled and has inflated
        the number of cores in /proc/cpuinfo)
    """
    physical_cpus = _find_physical_cpus()

    core_count = 0

    for num in physical_cpus:
        # Some architectures, e.g. x86_64, include a field for core count.
        # Since we found unique physical CPU entries, we can sum their core counts.
        if 'cpu cores' in physical_cpus[num]:
            core_count += int(physical_cpus[num]['cpu cores'])
        else:
            core_count += 1

    return core_count
