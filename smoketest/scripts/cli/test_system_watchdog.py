#!/usr/bin/env python3
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
from vyos.utils.process import cmd

base_path = ['system', 'watchdog']


class TestSystemWatchdog(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()
        super().tearDown()

    def test_enable_watchdog_softdog(self):
        """Configure watchdog (presence enables) with softdog and check state"""
        # Presence of 'system watchdog' enables watchdog; set module to softdog
        self.cli_set(base_path)
        self.cli_set(base_path + ['module', 'softdog'])
        self.cli_commit()
        # Check if softdog module is loaded
        lsmod = cmd('lsmod')
        self.assertIn('softdog', lsmod)
        # Check /dev/watchdog0 exists
        self.assertTrue(
            os.path.exists('/dev/watchdog0'), '/dev/watchdog0 does not exist'
        )
        # Check systemd config file exists
        config_path = '/run/systemd/system.conf.d/watchdog.conf'
        self.assertTrue(
            os.path.exists(config_path), f"Systemd config file not found: {config_path}"
        )

    def test_invalid_module_rejected(self):
        """Verify that a non-existent watchdog module causes commit failure"""
        # Choose a module name unlikely to exist; include a prefix to avoid collision with real names
        bogus_module = 'zzzx_watchdog_unit_test_fake'
        self.cli_set(base_path)

        # Module validation is preferred at set-time. Depending on the test harness,
        # this may raise on cli_set() or on cli_commit(). Accept either.
        try:
            self.cli_set(base_path + ['module', bogus_module])
        except Exception as e:
            self.assertRegex(
                str(e), r"Module must be an available watchdog kernel driver module"
            )
            return

        # If set-time validation did not trigger, commit-time validation must.
        with self.assertRaisesRegex(
            Exception,
            r"Watchdog( driver)? module '.*' was not found or cannot be loaded",
        ):
            self.cli_commit()

    def test_timeout_upper_limit(self):
        """Verify watchdog timeout upper bound (65535) is enforced"""
        self.cli_set(base_path)
        self.cli_set(base_path + ['module', 'softdog'])

        # 65535 must be accepted
        self.cli_set(base_path + ['timeout', '65535'])
        self.cli_commit()

        # 65536 must be rejected (ideally at set-time by XML validator)
        try:
            self.cli_set(base_path + ['timeout', '65536'])
        except Exception as e:
            # Error message depends on validator/harness formatting
            self.assertRegex(str(e), r"65535|Timeout must be between")
            return

        with self.assertRaisesRegex(Exception, r"65535|Timeout must be between"):
            self.cli_commit()

    def test_shutdown_and_reboot_timeout_written(self):
        """Verify shutdown-timeout and reboot-timeout are applied to systemd config"""
        self.cli_set(base_path)
        self.cli_set(base_path + ['module', 'softdog'])

        # Lowest valid values
        self.cli_set(base_path + ['shutdown-timeout', '60'])
        self.cli_set(base_path + ['reboot-timeout', '60'])
        self.cli_commit()

        config_path = '/run/systemd/system.conf.d/watchdog.conf'
        with open(config_path, 'r') as f:
            conf = f.read()
        self.assertIn('ShutdownWatchdogSec=60', conf)
        self.assertIn('RebootWatchdogSec=60', conf)

        # Highest valid values
        self.cli_set(base_path + ['shutdown-timeout', '65535'])
        self.cli_set(base_path + ['reboot-timeout', '65535'])
        self.cli_commit()

        with open(config_path, 'r') as f:
            conf = f.read()
        self.assertIn('ShutdownWatchdogSec=65535', conf)
        self.assertIn('RebootWatchdogSec=65535', conf)

    def test_shutdown_and_reboot_timeout_lower_bound(self):
        """Verify shutdown-timeout/reboot-timeout enforce lower bound (60)"""
        self.cli_set(base_path)
        self.cli_set(base_path + ['module', 'softdog'])
        self.cli_commit()

        for key in ['shutdown-timeout', 'reboot-timeout']:
            try:
                self.cli_set(base_path + [key, '59'])
            except Exception as e:
                self.assertRegex(
                    str(e), r"60|timeout must be between|Timeout must be between"
                )
                continue

            with self.assertRaisesRegex(
                Exception, r"60|timeout must be between|Timeout must be between"
            ):
                self.cli_commit()


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
