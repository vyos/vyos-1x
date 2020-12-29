#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

import re
import platform
import unittest

from vyos.util import read_file

kernel = platform.release()
config = read_file(f'/boot/config-{kernel}')

class TestKernelModules(unittest.TestCase):
    """ VyOS makes use of a lot of Kernel drivers, modules and features. The
    required modules which are essential for VyOS should be tested that they are
    available in the Kernel that is run. """

    def test_bond_interface(self):
        """ The bond/lacp interface must be enabled in the OS Kernel """
        for option in ['CONFIG_BONDING']:
            tmp = re.findall(f'{option}=(y|m)', config)
            self.assertTrue(tmp)

    def test_bridge_interface(self):
        """ The bridge interface must be enabled in the OS Kernel """
        for option in ['CONFIG_BRIDGE',
                       'CONFIG_BRIDGE_IGMP_SNOOPING',
                       'CONFIG_BRIDGE_VLAN_FILTERING']:
            tmp = re.findall(f'{option}=(y|m)', config)
            self.assertTrue(tmp)

    def test_qemu_support(self):
        """ The bond/lacp interface must be enabled in the OS Kernel """
        for option in ['CONFIG_VIRTIO_BLK', 'CONFIG_SCSI_VIRTIO',
                       'CONFIG_VIRTIO_NET', 'CONFIG_VIRTIO_CONSOLE',
                       'CONFIG_VIRTIO', 'CONFIG_VIRTIO_PCI',
                       'CONFIG_VIRTIO_BALLOON', 'CONFIG_CRYPTO_DEV_VIRTIO',
                       'CONFIG_X86_PLATFORM_DEVICES']:
            tmp = re.findall(f'{option}=(y|m)', config)
            self.assertTrue(tmp)

    def test_vmware_support(self):
        """ The bond/lacp interface must be enabled in the OS Kernel """
        for option in ['CONFIG_VMXNET3']:
            tmp = re.findall(f'{option}=(y|m)', config)
            self.assertTrue(tmp)

if __name__ == '__main__':
    unittest.main(verbosity=2)

