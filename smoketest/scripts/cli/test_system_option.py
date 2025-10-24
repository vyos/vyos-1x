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
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.cpu import get_cpus
from vyos.utils.file import read_file
from vyos.utils.process import is_systemd_service_active
from vyos.utils.system import sysctl_read
from vyos.system import image

base_path = ['system', 'option']

class TestSystemOption(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()
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

        self.assertEqual(sysctl_read('net.ipv4.neigh.default.gc_thresh1'), gc_thresh1)
        self.assertEqual(sysctl_read('net.ipv4.neigh.default.gc_thresh2'), gc_thresh2)
        self.assertEqual(sysctl_read('net.ipv4.neigh.default.gc_thresh3'), gc_thresh3)

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
        isolate_cpus = '1,2,3'
        nohz_full = '2'
        rcu_no_cbs = '1,2,4-5'

        self.cli_set(['system', 'option', 'kernel', 'cpu', 'disable-nmi-watchdog'])
        self.cli_set(['system', 'option', 'kernel', 'cpu', 'isolate-cpus', isolate_cpus])
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
        tmp = read_file(f'{image.grub.GRUB_DIR_VYOS_VERS}/{image.get_running_image()}.cfg')
        self.assertIn(' mitigations=off', tmp)
        self.assertIn(' intel_idle.max_cstate=0 processor.max_cstate=1', tmp)
        self.assertIn(' quiet', tmp)
        self.assertIn(' nmi_watchdog=0', tmp)
        self.assertIn(' hpet=disable', tmp)
        self.assertIn(' mce=off', tmp)
        self.assertIn(' nosoftlockup', tmp)
        self.assertIn(f' isolcpus={isolate_cpus}', tmp)
        self.assertIn(f' nohz_full={nohz_full}', tmp)
        self.assertIn(f' rcu_nocbs={rcu_no_cbs}', tmp)
        self.assertIn(' numa_balancing=disable', tmp)

        if cpu_vendor == 'AuthenticAMD':
            self.assertIn(f' initcall_blacklist=acpi_cpufreq_init amd_pstate={amd_pstate_mode}', tmp)

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
