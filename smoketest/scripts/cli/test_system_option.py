#!/usr/bin/env python3
#
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

import os
import subprocess
import unittest
import tempfile

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.defaults import systemd_services
from vyos.defaults import KDUMP_DEFAULT_MEMORY_AUTO
from vyos.utils.cpu import get_cpus
from vyos.utils.file import read_file
from vyos.utils.file import write_file
from vyos.utils.process import is_systemd_service_active
from vyos.utils.system import sysctl_read
from vyos.system import image

base_path = ['system', 'option']
kdump_path = base_path + ['kdump']


def _get_grub_config():
    """Read GRUB config file for current running image"""
    return read_file(f'{image.grub.GRUB_DIR_VYOS_VERS}/{image.get_running_image()}.cfg')

class TestSystemOption(VyOSUnitTestSHIM.TestCase):
    def setUp(self):
        self.tmp_path = tempfile.TemporaryDirectory(prefix='system-option-test-')

        # always forward to base class
        super().setUp()

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()
        self.tmp_path.cleanup()

        # always forward to base class
        super().tearDown()

    def test_ctrl_alt_delete(self):
        self.cli_set(base_path + ['ctrl-alt-delete', 'reboot'])
        self.cli_commit()

        tmp = os.readlink('/lib/systemd/system/ctrl-alt-del.target')
        self.assertEqual(tmp, '/lib/systemd/system/reboot.target')

        self.cli_set(base_path + ['ctrl-alt-delete', 'poweroff'])
        self.cli_commit()

        tmp = os.readlink('/lib/systemd/system/ctrl-alt-del.target')
        self.assertEqual(tmp, '/lib/systemd/system/poweroff.target')

        self.cli_delete(base_path + ['ctrl-alt-delete', 'poweroff'])
        self.cli_commit()
        self.assertFalse(os.path.exists('/lib/systemd/system/ctrl-alt-del.target'))

    def test_reboot_on_panic(self):
        panic_file = '/proc/sys/kernel/panic'

        tmp = read_file(panic_file)
        self.assertEqual(tmp, '0')

        self.cli_set(base_path + ['reboot-on-panic'])
        self.cli_commit()

        tmp = read_file(panic_file)
        self.assertEqual(tmp, '60')

    def test_performance(self):
        tuned_service = 'tuned.service'
        path = ['system', 'sysctl', 'parameter']

        self.assertFalse(is_systemd_service_active(tuned_service))

        # T3204 sysctl options must not be overwritten by tuned
        gc_thresh1 = '131072'
        gc_thresh2 = '262000'
        gc_thresh3 = '524000'

        self.cli_set(path + ['net.ipv4.neigh.default.gc_thresh1', 'value', gc_thresh1])
        self.cli_set(path + ['net.ipv4.neigh.default.gc_thresh2', 'value', gc_thresh2])
        self.cli_set(path + ['net.ipv4.neigh.default.gc_thresh3', 'value', gc_thresh3])

        self.cli_set(base_path + ['performance', 'network-throughput'])
        self.cli_commit()

        self.assertTrue(is_systemd_service_active(tuned_service))

        self.assertEqual(sysctl_read(['net', 'ipv4', 'neigh', 'default', 'gc_thresh1']), gc_thresh1)
        self.assertEqual(sysctl_read(['net', 'ipv4', 'neigh', 'default', 'gc_thresh2']), gc_thresh2)
        self.assertEqual(sysctl_read(['net', 'ipv4', 'neigh', 'default', 'gc_thresh3']), gc_thresh3)

    def test_ssh_client_options(self):
        loopback = 'lo'
        ssh_client_opt_file = '/etc/ssh/ssh_config.d/91-vyos-ssh-client-options.conf'

        self.cli_set(['system', 'option', 'ssh-client', 'source-interface', loopback])
        self.cli_commit()

        tmp = read_file(ssh_client_opt_file)
        self.assertEqual(tmp, f'BindInterface {loopback}')

        self.cli_delete(['system', 'option'])
        self.cli_commit()
        self.assertFalse(os.path.exists(ssh_client_opt_file))

    def test_kernel_options(self):
        amd_pstate_mode = 'active'
        nohz_full = '2'
        rcu_no_cbs = '1,2,4-5'

        self.cli_set(['system', 'option', 'kernel', 'cpu', 'disable-nmi-watchdog'])
        self.cli_set(['system', 'option', 'kernel', 'cpu', 'nohz-full', nohz_full])
        self.cli_set(['system', 'option', 'kernel', 'cpu', 'rcu-no-cbs', rcu_no_cbs])
        self.cli_set(['system', 'option', 'kernel', 'disable-hpet'])
        self.cli_set(['system', 'option', 'kernel', 'disable-mce'])
        self.cli_set(['system', 'option', 'kernel', 'disable-mitigations'])
        self.cli_set(['system', 'option', 'kernel', 'disable-power-saving'])
        self.cli_set(['system', 'option', 'kernel', 'disable-softlockup'])
        self.cli_set(['system', 'option', 'kernel', 'memory', 'disable-numa-balancing'])
        self.cli_set(['system', 'option', 'kernel', 'quiet'])

        self.cli_set(['system', 'option', 'kernel', 'amd-pstate-driver', amd_pstate_mode])
        cpu_vendor = get_cpus()[0]['vendor_id']
        if cpu_vendor != 'AuthenticAMD':
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_delete(['system', 'option', 'kernel', 'amd-pstate-driver'])

        self.cli_commit()

        # Read GRUB config file for current running image
        tmp = _get_grub_config()
        self.assertIn(' mitigations=off', tmp)
        self.assertIn(' intel_idle.max_cstate=0 processor.max_cstate=1', tmp)
        self.assertIn(' quiet', tmp)
        self.assertIn(' nmi_watchdog=0', tmp)
        self.assertIn(' hpet=disable', tmp)
        self.assertIn(' mce=off', tmp)
        self.assertIn(' nosoftlockup', tmp)
        self.assertIn(f' nohz_full={nohz_full}', tmp)
        self.assertIn(f' rcu_nocbs={rcu_no_cbs}', tmp)
        self.assertIn(' numa_balancing=disable', tmp)

        if cpu_vendor == 'AuthenticAMD':
            self.assertIn(f' initcall_blacklist=acpi_cpufreq_init amd_pstate={amd_pstate_mode}', tmp)

    def test_fips(self):
        # Enable FIPS
        self.cli_set(['system', 'option', 'fips'])
        self.cli_commit()

        # Verify OpenSSL config is updated
        tmp = read_file('/etc/ssl/openssl.cnf')
        self.assertIn('.include /run/ssl/fipsmodule.cnf', tmp)
        self.assertIn('fips = fips_sect', tmp)

        # Verify OpenSSL provider is active
        out = subprocess.check_output(['openssl', 'list', '-providers'], text=True)

        self.assertIn('fips', out)
        self.assertIn('OpenSSL FIPS Provider', out)
        self.assertIn('status: active', out)

        # Remove FIPS
        self.cli_delete(['system', 'option'])
        self.cli_commit()

        # Verify config cleanup
        tmp = read_file('/etc/ssl/openssl.cnf')
        self.assertNotIn('.include /run/ssl/fipsmodule.cnf', tmp)
        self.assertNotIn('fips = fips_sect', tmp)

        # Verify FIPS provider is no longer active
        out = subprocess.check_output(['openssl', 'list', '-providers'], text=True)
        self.assertNotIn('OpenSSL FIPS Provider', out)

    def test_kdump_base(self):
        # Test basic kdump functionality

        dump_path = self.tmp_path.name
        service = systemd_services['kdump']
        config_file = '/etc/default/kdump-tools'
        initramfs_hook = '/etc/initramfs-tools/conf.d/zzzz-kdump-vyos-overlay'

        self.cli_set(kdump_path + ['dump-path', dump_path])
        self.cli_commit()

        self.assertTrue(
            os.path.exists(config_file),
            'kdump-tools config file was not created after enabling kdump',
        )

        self.assertTrue(
            os.path.exists(initramfs_hook),
            'initramfs conf.d hook was not created after enabling kdump',
        )

        hook_content = read_file(initramfs_hook)
        self.assertIn(
            'MODULES=most',
            hook_content,
            'initramfs hook must contain MODULES=most to work on OverlayFS root',
        )

        self.assertTrue(
            is_systemd_service_active(service),
            f'{service} must be active after enabling kdump',
        )

        # Disabling kdump must remove the initramfs conf.d drop-in
        self.cli_delete(kdump_path)
        self.cli_commit()

        self.assertFalse(
            os.path.exists(initramfs_hook),
            'initramfs hook must be removed after disabling kdump',
        )

        self.assertTrue(
            os.path.exists(config_file),
            'kdump-tools config file must still exist after disabling kdump',
        )
        config_content = read_file(config_file)
        self.assertIn(
            'USE_KDUMP=0',
            config_content,
            'Disabled kdump-tools config must contain USE_KDUMP=0',
        )

    def test_kdump_memory(self):
        # Test memory reservation logic

        memory = '128'
        self.cli_set(kdump_path + ['memory', memory])
        self.cli_commit()

        grub_cfg = _get_grub_config()
        self.assertIn(
            f'crashkernel={memory}',
            grub_cfg,
            '`crashkernel` value not found in GRUB config after setting explicit memory',
        )

        # Tiered crashkernel= value produced when memory is set to 'auto'
        auto_memory = KDUMP_DEFAULT_MEMORY_AUTO

        self.cli_set(kdump_path + ['memory', 'auto'])
        self.cli_commit()

        grub_cfg = _get_grub_config()
        self.assertIn(
            f'crashkernel={auto_memory}',
            grub_cfg,
            "'memory auto' did not produce the expected tiered `crashkernel` value in GRUB config",
        )

    def test_kdump_memory_error(self):
        # Test special cases where invalid memory range values should raise an error

        special_cases = (
            '1',  # Invalid low value
            '1048570',  # ~1TB which often more then available RAM
        )
        for case in special_cases:
            with self.subTest(case=case):
                with self.assertRaises(ConfigSessionError):
                    self.cli_set(kdump_path + ['memory', case])
                    self.cli_commit()

    def test_op_show_kdump_status(self):
        # Test operational mode command 'show system kdump'

        result = self.op_mode(['show', 'system', 'kdump'])
        self.assertIn('not configured', result)

        memory = '256'
        self.cli_set(kdump_path + ['memory', memory])
        self.cli_commit()

        result = self.op_mode(['show', 'system', 'kdump'])
        self.assertIn('Crash kernel', result)
        self.assertIn(memory, result)

    def test_op_show_kdump_dumps(self):
        # Test operational mode command 'show system kdump dumps'
        dump_path = self.tmp_path.name

        self.cli_set(kdump_path + ['dump-path', dump_path])
        self.cli_commit()

        result = self.op_mode(['show', 'system', 'kdump', 'dumps'])
        self.assertIn('No kernel crash dumps recorded', result)

        timestamp1 = '202607070802'
        timestamp2 = '202607070939'

        for ts in (timestamp1, timestamp2):
            sub = os.path.join(dump_path, ts)
            os.makedirs(sub)

            # Write a small synthetic vmcore so the size check is non-trivial
            write_file(os.path.join(sub, f'dump.{ts}'), '0' * 1024)
            write_file(os.path.join(sub, f'dmesg.{ts}'), f'synthetic dmesg {ts}')

        result = self.op_mode(['show', 'system', 'kdump', 'dumps'])

        self.assertIn(f'{dump_path}/{timestamp1}', result)
        self.assertIn(f'{dump_path}/{timestamp2}', result)


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
