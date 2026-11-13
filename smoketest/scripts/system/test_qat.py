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
# are meaningful on the hardware-free images used by CI.

import os
import re
import tempfile
import unittest

from subprocess import run
from subprocess import PIPE
from unittest.mock import patch

from vyos import qat
from vyos.defaults import directories

op_mode_script = os.path.join(directories['op_mode'], 'show_acceleration.py')

ADF_CTL_STATUS = """Checking status of all devices.
There is 3 QAT acceleration device(s) in the system:
 qat_dev0 - type: c3xxx,  inst_id: 0,  node_id: 0,  bsf: 0000:01:00.0,  #accel: 3 #engines: 6 state: up
 qat_dev1 - type: c6xx,  inst_id: 0,  node_id: 0,  bsf: 0000:3d:00.0,  #accel: 5 #engines: 10 state: down
 qat_dev10 - type: c6xxvf,  inst_id: 7,  node_id: 0,  bsf: 0000:3d:01.7,  #accel: 1 #engines: 1 state: up
"""


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


class TestQATDriverStatus(unittest.TestCase):
    def test_device_lines(self):
        devices = qat.parse_adf_ctl_status(ADF_CTL_STATUS)
        self.assertEqual(
            [device['name'] for device in devices],
            ['qat_dev0', 'qat_dev1', 'qat_dev10'],
        )
        self.assertEqual(
            devices[1],
            {
                'name': 'qat_dev1',
                'type': 'c6xx',
                'address': '0000:3d:00.0',
                'state': 'down',
            },
        )

    def test_short_address(self):
        # The short form shown in Intel's documentation, with no PCI domain.
        line = 'qat_dev0 - type: c6xx, inst_id: 0, bsf: 06:00:0, #accel: 5 #engines: 10 state: up'
        devices = qat.parse_adf_ctl_status(line)
        self.assertEqual([device['address'] for device in devices], ['0000:06:00.0'])

    def test_canonical_pci_address(self):
        for address, expected in (
            ('06:00:0', '0000:06:00.0'),
            ('0000:3D:01.7', '0000:3d:01.7'),
            ('0001:5e:00.1', '0001:5e:00.1'),
            ('garbage', 'garbage'),
        ):
            self.assertEqual(qat.canonical_pci_address(address), expected)

    def test_query(self):
        with patch.object(qat, 'rc_cmd', return_value=(0, ADF_CTL_STATUS)) as rc_cmd:
            devices = qat.get_driver_status()

        rc_cmd.assert_called_once_with(f'{qat.ADF_CTL} status')
        self.assertEqual(len(devices), 3)

    def test_query_fails(self):
        result = (127, 'sh: 1: /usr/sbin/adf_ctl: not found')
        with patch.object(qat, 'rc_cmd', return_value=result):
            self.assertEqual(qat.get_driver_status(), [])


class TestQATDeviceState(unittest.TestCase):
    # get_device_state() is a pure function of its arguments, so every state
    # can be checked without the corresponding hardware.
    driver_status = qat.parse_adf_ctl_status(ADF_CTL_STATUS)

    def state(self, address, driver='c6xx'):
        device = {'address': address, 'driver': driver}
        return qat.get_device_state(device, self.driver_status)

    def test_no_driver_bound(self):
        self.assertEqual(
            self.state('0000:01:00.0', driver=None), qat.DEVICE_STATE_NO_DRIVER
        )

    def test_started(self):
        self.assertEqual(self.state('0000:01:00.0'), qat.DEVICE_STATE_STARTED)

    def test_stopped(self):
        # Still bound, so its debugfs directory is still there. Only the
        # driver can tell that it is not running.
        self.assertEqual(self.state('0000:3d:00.0'), qat.DEVICE_STATE_NOT_STARTED)

    def test_same_bus_as_stopped_device(self):
        self.assertEqual(self.state('0000:3d:01.7'), qat.DEVICE_STATE_STARTED)

    def test_short_address(self):
        status = 'qat_dev0 - type: c6xx, inst_id: 0, bsf: 06:00:0, #accel: 5 #engines: 10 state: down'
        device = {'address': '0000:06:00.0', 'driver': 'c6xx'}
        self.assertEqual(
            qat.get_device_state(device, qat.parse_adf_ctl_status(status)),
            qat.DEVICE_STATE_NOT_STARTED,
        )

    def test_address_case(self):
        self.assertEqual(self.state('0000:3D:00.0'), qat.DEVICE_STATE_NOT_STARTED)

    def test_not_listed_by_driver(self):
        self.assertEqual(self.state('0000:99:00.0'), qat.DEVICE_STATE_UNKNOWN)

    def test_driver_cannot_be_queried(self):
        device = {'address': '0000:01:00.0', 'driver': 'c3xxx'}
        self.assertEqual(qat.get_device_state(device, []), qat.DEVICE_STATE_UNKNOWN)


class TestQATDiscovery(unittest.TestCase):
    def add_pci_device(self, root, address, vendor, device, driver=None):
        path = os.path.join(root, address)
        os.mkdir(path)
        for name, value in (('vendor', vendor), ('device', device)):
            with open(os.path.join(path, name), 'w') as f:
                f.write(f'{value}\n')
        if driver:
            target = f'../../../bus/pci/drivers/{driver}'
            os.symlink(target, os.path.join(path, 'driver'))

    def test_find_devices(self):
        with tempfile.TemporaryDirectory() as root:
            self.add_pci_device(root, '0000:00:00.0', '0x8086', '0x1533', 'igb')
            self.add_pci_device(root, '0000:00:01.0', '0x10de', '0x18ee')
            self.add_pci_device(root, '0000:01:00.0', '0x8086', '0x18ee', '200xx')
            self.add_pci_device(root, '0000:02:00.0', '0x8086', '0x37c8')

            with patch.object(qat, 'PCI_DEVICES_PATH', root):
                devices = qat.find_devices()

        self.assertEqual(
            devices,
            [
                {
                    'address': '0000:01:00.0',
                    'chipset': 'QAT_200XX',
                    'driver': '200xx',
                },
                {'address': '0000:02:00.0', 'chipset': 'C62x', 'driver': None},
            ],
        )

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
        proc_crypto = (
            'name         : authenc(hmac(sha256),cbc(aes))\n'
            'driver       : qat_aes_cbc_hmac_sha256\n'
            'module       : intel_qat\n'
            '\n'
            'name         : __cbc(aes)\n'
            'driver       : __cbc-aes-aesni\n'
            'module       : aesni_intel\n'
            '\n'
            'name         : pkcs1pad(rsa,sha256)\n'
            'driver       : pkcs1pad(qat-rsa,sha256)\n'
            'module       : kernel\n'
        )
        with patch.object(qat, 'read_file', return_value=proc_crypto):
            algorithms = qat.get_crypto_algorithms()

        self.assertEqual(
            [algorithm['driver'] for algorithm in algorithms],
            ['qat_aes_cbc_hmac_sha256', 'pkcs1pad(qat-rsa,sha256)'],
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
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_option_prints_help(self):
        result = run([op_mode_script], stdout=PIPE, stderr=PIPE)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'usage:', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
