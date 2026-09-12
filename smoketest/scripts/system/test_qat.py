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

# These tests cover the QAT device discovery helpers and the option surface of
# the op-mode script. They deliberately do not require a QAT device, so they
# are meaningful on the hardware-free images used by CI. Anything that needs
# real acceleration hardware is called out in the individual test.

import os
import re
import unittest

from subprocess import run
from subprocess import PIPE

from vyos import qat
from vyos.defaults import directories

op_mode_script = os.path.join(directories['op_mode'], 'show_acceleration.py')


class TestQATDeviceIDs(unittest.TestCase):
    def test_table_is_well_formed(self):
        self.assertTrue(qat.PCI_DEVICE_IDS)
        for device_id, chipset in qat.PCI_DEVICE_IDS.items():
            self.assertRegex(device_id, r'^0x[0-9a-f]{4}$')
            self.assertTrue(chipset)

    def test_qat_200xx_is_supported(self):
        # 8086:18ee was added to the conf-mode PCI ID list in 2020 but never to
        # the op-mode one, so "set system acceleration qat" committed while
        # "show system acceleration qat" reported that no device was present.
        # Both now read this table, so the two can no longer disagree.
        self.assertIn('0x18ee', qat.PCI_DEVICE_IDS)


class TestQATDeviceState(unittest.TestCase):
    # get_device_state() is a pure function over a device dictionary, so every
    # state can be checked without the corresponding hardware.
    def test_no_driver_bound(self):
        device = {'driver': None, 'debugfs': None}
        self.assertEqual(qat.get_device_state(device), qat.DEVICE_STATE_NO_DRIVER)

    def test_started(self):
        device = {'driver': '200xx', 'debugfs': '/sys/kernel/debug/qat_200xx_x'}
        self.assertEqual(qat.get_device_state(device), qat.DEVICE_STATE_STARTED)

    def test_bound_but_not_started(self):
        device = {'driver': '200xx', 'debugfs': None}
        expected = (
            qat.DEVICE_STATE_NOT_STARTED
            if qat.debugfs_mounted()
            else qat.DEVICE_STATE_UNKNOWN
        )
        self.assertEqual(qat.get_device_state(device), expected)

    def test_states_are_distinct(self):
        # The whole point of the report is that a bound-but-unconfigured
        # device is not indistinguishable from an absent one.
        states = {
            qat.DEVICE_STATE_NO_DRIVER,
            qat.DEVICE_STATE_NOT_STARTED,
            qat.DEVICE_STATE_STARTED,
            qat.DEVICE_STATE_UNKNOWN,
        }
        self.assertEqual(len(states), 4)


class TestQATDiscovery(unittest.TestCase):
    def test_find_devices(self):
        # Returns an empty list on images without QAT hardware. What matters
        # here is that it never raises and that entries are well formed.
        for device in qat.find_devices():
            for key in ['address', 'chipset', 'driver', 'debugfs']:
                self.assertIn(key, device)
            self.assertIn(device['chipset'], qat.PCI_DEVICE_IDS.values())

    def test_proc_crypto_is_parsable(self):
        # Guards the parser against changes in the kernel's /proc/crypto
        # layout. Every kernel registers at least one algorithm.
        from vyos.utils.file import read_file

        entries = list(qat._parse_proc_crypto(read_file(qat.PROC_CRYPTO)))
        self.assertTrue(entries)
        for entry in entries:
            self.assertIn('name', entry)
            self.assertIn('driver', entry)

    def test_crypto_algorithms(self):
        # Empty unless the QAT driver registered with the kernel crypto
        # framework, which requires QAT hardware and an LKCF-enabled driver.
        for algorithm in qat.get_crypto_algorithms():
            self.assertTrue(
                'qat' in algorithm.get('driver', '')
                or 'qat' in algorithm.get('module', '')
            )


class TestQATOpMode(unittest.TestCase):
    def test_options_use_hyphens(self):
        # The op-mode definition calls this script with hyphenated options.
        # An underscore in a declaration silently breaks that call site, which
        # is what happened to --dev-list.
        with open(op_mode_script) as f:
            source = f.read()

        options = re.findall(r'add_argument\(\s*["\'](--[^"\']+)', source)
        self.assertTrue(options)
        for option in options:
            self.assertNotIn('_', option, f'{option} must use hyphens')

    def test_dev_list_option_accepted(self):
        # Regression test: this is the completion helper for
        # "show system acceleration qat device <tab>".
        result = run([op_mode_script, '--dev-list'], stdout=PIPE, stderr=PIPE)
        self.assertNotIn(b'unrecognized arguments', result.stderr)

    def test_no_option_prints_help(self):
        result = run([op_mode_script], stdout=PIPE, stderr=PIPE)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'usage:', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
