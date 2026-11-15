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
from unittest import mock

import vyos.system.image
import vyos.utils.kernel
from vyos import ConfigError
from vyos.defaults import KDUMP_DEFAULT_MEMORY_AUTO
from vyos.utils.kernel import check_kmod
from vyos.utils.kernel import get_kernel_cmdline_options
from vyos.utils.kernel import verify_kmod

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

    def _container(self, value):
        return mock.patch.object(vyos.system.image, 'is_running_as_container',
                                 return_value=value)

    def _available(self, available):
        return mock.patch.object(vyos.utils.kernel, 'is_module_available',
                                 side_effect=lambda module: module in available)

    def test_verify_kmod_no_container(self):
        with self._container(False), self._available([]) as probe:
            verify_kmod(['wireguard'])
            probe.assert_not_called()

    def test_verify_kmod_container_available(self):
        with self._container(True), self._available(['l2tp_eth', 'l2tp_ip']):
            verify_kmod('l2tp_eth l2tp_ip')

    def test_verify_kmod_container_missing(self):
        with self._container(True), self._available(['l2tp_eth']):
            with self.assertRaisesRegex(ConfigError, 'modprobe l2tp_ip'):
                verify_kmod(['l2tp_eth', 'l2tp_ip'])

    def test_check_kmod_container_skips_modprobe(self):
        with self._container(True), \
             mock.patch.object(vyos.utils.kernel, 'load_module') as load:
            check_kmod(['wireguard'])
            load.assert_not_called()

    def test_check_kmod_no_container_loads(self):
        with self._container(False), \
             mock.patch.object(vyos.utils.kernel, 'load_module',
                               return_value=0) as load:
            check_kmod('wireguard')
            load.assert_called_once_with('wireguard')

    def test_is_module_available_unknown_module(self):
        with mock.patch.object(vyos.utils.kernel, 'is_module_loaded',
                               return_value=False):
            self.assertFalse(vyos.utils.kernel.is_module_available('vyos_none'))

    def test_is_module_available_nft_probe(self):
        with mock.patch.object(vyos.utils.kernel, 'is_module_loaded',
                               return_value=False):
            for rc, expected in [(0, True), (1, False)]:
                with mock.patch('vyos.utils.process.run', return_value=rc) as run:
                    self.assertEqual(
                        vyos.utils.kernel.is_module_available('nft_nat'), expected)
                    run.assert_called_once_with(
                        ['nft', '-c', '-f', '-'],
                        input=vyos.utils.kernel.KMOD_NFT_PROBE['nft_nat'])


if __name__ == '__main__':
    unittest.main()
