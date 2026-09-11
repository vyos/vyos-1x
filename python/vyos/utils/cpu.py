# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

import os
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


def get_available_cpus():
    """ List of cpus with ids that are available in the system
        Uses 'lscpu' command

        Returns: list[dict[str, str | int | bool]]: cpus details
    """
    import json

    from vyos.utils.process import cmdl

    out = json.loads(cmdl(['lscpu', '--extended', '-b', '--json']))

    return out['cpus']


def get_half_cpus():
    """ return 1/2 of the numbers of available CPUs """
    return max(1, os.cpu_count() // 2)


# Aliases for the architecture names reported by platform.machine()
_arch_alias = {
    'x86_64': 'amd64',
    'amd64': 'amd64',
    'aarch64': 'arm64',
    'arm64': 'arm64',
}

def _normalize_arch(arch):
    return _arch_alias.get(arch.lower(), arch.lower())

def get_cpu_arch():
    """ Returns the normalized CPU architecture of the running system,
        e.g. "amd64" or "arm64". Architectures we do not know about are
        returned as reported by platform.machine()
    """
    import platform

    return _normalize_arch(platform.machine())

def cpu_arch(*architectures):
    """ Decorator restricting a unittest TestCase or test method to a list
        of CPU architectures. If the current architecture is not supported,
        the test is skipped instead of failing.

        Both the native names (x86_64, aarch64) and the Debian names
        (amd64, arm64) are accepted.

        Usage:
            @cpu_arch('amd64')
            def test_intel_modules(self):
                ...

            @cpu_arch('amd64', 'arm64')
            class TestFoo(unittest.TestCase):
                ...
    """
    import unittest

    # Allow both cpu_arch('amd64', 'arm64') and cpu_arch(['amd64', 'arm64'])
    if len(architectures) == 1 and isinstance(architectures[0], (list, tuple, set)):
        architectures = tuple(architectures[0])

    supported = {_normalize_arch(arch) for arch in architectures}
    current = get_cpu_arch()

    reason = (f'Only supported on CPU architecture: {", ".join(sorted(supported))} '
              f'(running on {current})')

    return unittest.skipUnless(current in supported, reason)
