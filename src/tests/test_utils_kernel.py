# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import unittest

from vyos.defaults import KDUMP_DEFAULT_MEMORY_AUTO
from vyos.utils.kernel import get_kernel_cmdline_options

# What recursive defaults add to "system option" when nothing is configured
KDUMP_DEFAULTS = {'kdump': {'memory': 'auto', 'dump_path': '/var/crash'}}


class TestVyOSUtilsKernel(unittest.TestCase):
    def test_cmdline_options_empty(self):
        self.assertEqual(get_kernel_cmdline_options({}, kdump_enabled=False), [])

    def test_cmdline_options_kdump_disabled(self):
        self.assertEqual(
            get_kernel_cmdline_options(KDUMP_DEFAULTS, kdump_enabled=False), []
        )

    def test_cmdline_options_kdump_auto(self):
        self.assertEqual(
            get_kernel_cmdline_options(KDUMP_DEFAULTS, kdump_enabled=True),
            [f'crashkernel={KDUMP_DEFAULT_MEMORY_AUTO}'],
        )

    def test_cmdline_options_kdump_memory(self):
        options = {'kdump': {'memory': '512'}}
        self.assertEqual(
            get_kernel_cmdline_options(options, kdump_enabled=True),
            ['crashkernel=512M'],
        )

    def test_cmdline_options_all(self):
        options = {
            'reboot_on_panic': {},
            'kernel': {
                'disable_mitigations': {},
                'disable_power_saving': {},
                'amd_pstate_driver': 'active',
                'quiet': {},
                'disable_hpet': {},
                'disable_mce': {},
                'disable_softlockup': {},
                'cpu': {
                    'isolate_cpus': '1-3',
                    'nohz_full': '1-3',
                    'rcu_no_cbs': '1-3',
                    'disable_nmi_watchdog': {},
                },
                'memory': {
                    'disable_numa_balancing': {},
                    'default_hugepage_size': '2M',
                    'hugepage_size': {
                        '2M': {'hugepage_count': '512'},
                        '1G': {'hugepage_count': '4'},
                    },
                },
            },
            **KDUMP_DEFAULTS,
        }
        self.assertEqual(
            get_kernel_cmdline_options(options, kdump_enabled=True),
            [
                'mitigations=off',
                'intel_idle.max_cstate=0 processor.max_cstate=1',
                'initcall_blacklist=acpi_cpufreq_init amd_pstate=active',
                'quiet',
                'panic=60',
                'hpet=disable',
                'mce=off',
                'nosoftlockup',
                'isolcpus=1-3',
                'nohz_full=1-3',
                'rcu_nocbs=1-3',
                'nmi_watchdog=0',
                'numa_balancing=disable',
                'default_hugepagesz=2M',
                'hugepagesz=2M',
                'hugepages=512',
                'hugepagesz=1G',
                'hugepages=4',
                f'crashkernel={KDUMP_DEFAULT_MEMORY_AUTO}',
            ],
        )


if __name__ == '__main__':
    unittest.main()
