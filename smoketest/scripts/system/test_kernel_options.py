#!/usr/bin/env python3
#
# Copyright (C) 2020-2024 VyOS maintainers and contributors
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
import os
import platform
import unittest

from vyos.utils.kernel import check_kmod

kernel = platform.release()
class TestKernelModules(unittest.TestCase):
    """ VyOS makes use of a lot of Kernel drivers, modules and features. The
    required modules which are essential for VyOS should be tested that they are
    available in the Kernel that is run. """

    _config_data = None

    @classmethod
    def setUpClass(cls):
        import gzip
        from vyos.utils.process import call

        super(TestKernelModules, cls).setUpClass()
        CONFIG = '/proc/config.gz'
        if not os.path.isfile(CONFIG):
            check_kmod('configs')

        with gzip.open(CONFIG, 'rt') as f:
            cls._config_data = f.read()

    def test_bond_interface(self):
        # The bond/lacp interface must be enabled in the OS Kernel
        for option in ['CONFIG_BONDING']:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

    def test_bridge_interface(self):
        # The bridge interface must be enabled in the OS Kernel
        for option in ['CONFIG_BRIDGE',
                       'CONFIG_BRIDGE_IGMP_SNOOPING',
                       'CONFIG_BRIDGE_VLAN_FILTERING']:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

    def test_dropmon_enabled(self):
        options_to_check = [
            'CONFIG_NET_DROP_MONITOR=y',
            'CONFIG_UPROBE_EVENTS=y',
            'CONFIG_BPF_EVENTS=y',
            'CONFIG_TRACEPOINTS=y'
        ]

        for option in options_to_check:
            self.assertIn(option, self._config_data)

    def test_synproxy_enabled(self):
        options_to_check = [
            'CONFIG_NFT_SYNPROXY',
            'CONFIG_IP_NF_TARGET_SYNPROXY'
        ]
        for option in options_to_check:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

    def test_qemu_support(self):
        options_to_check = [
            'CONFIG_VIRTIO_BLK', 'CONFIG_SCSI_VIRTIO',
            'CONFIG_VIRTIO_NET', 'CONFIG_VIRTIO_CONSOLE',
            'CONFIG_VIRTIO', 'CONFIG_VIRTIO_PCI',
            'CONFIG_VIRTIO_BALLOON', 'CONFIG_CRYPTO_DEV_VIRTIO',
            'CONFIG_X86_PLATFORM_DEVICES'
            ]
        for option in options_to_check:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

    def test_vmware_support(self):
        for option in ['CONFIG_VMXNET3']:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

    def test_container_cgroup_support(self):
        options_to_check = [
            'CONFIG_CGROUPS', 'CONFIG_MEMCG',
            'CONFIG_CGROUP_PIDS', 'CONFIG_CGROUP_BPF'
            ]
        for option in options_to_check:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

    def test_ip_routing_support(self):
        options_to_check = [
            'CONFIG_IP_ADVANCED_ROUTER', 'CONFIG_IP_MULTIPLE_TABLES',
            'CONFIG_IP_ROUTE_MULTIPATH'
            ]
        for option in options_to_check:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

    def test_vfio(self):
        options_to_check = [
            'CONFIG_VFIO', 'CONFIG_VFIO_GROUP', 'CONFIG_VFIO_CONTAINER',
            'CONFIG_VFIO_IOMMU_TYPE1', 'CONFIG_VFIO_NOIOMMU', 'CONFIG_VFIO_VIRQFD'
            ]
        for option in options_to_check:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

    def test_container_cpu(self):
        options_to_check = [
            'CONFIG_CGROUP_SCHED', 'CONFIG_CPUSETS', 'CONFIG_CGROUP_CPUACCT', 'CONFIG_CFS_BANDWIDTH'
            ]
        for option in options_to_check:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

if __name__ == '__main__':
    unittest.main(verbosity=2)
