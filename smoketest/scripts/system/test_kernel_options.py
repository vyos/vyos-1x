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

import re
import os
import platform
import unittest

from vyos.utils.kernel import check_kmod

ARCH = platform.machine()
IS_ARM64 = ARCH in ('aarch64', 'arm64')
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
        for option in ['CONFIG_STP', 'CONFIG_BRIDGE',
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

    def test_psample_enabled(self):
        # Psample must be enabled in the OS Kernel to enable egress flow for hsflowd
        for option in ['CONFIG_PSAMPLE']:
            tmp = re.findall(f'{option}=y', self._config_data)
            self.assertTrue(tmp)

    def test_amd_pstate(self):
        # AMD pstate driver required as we have "set system option kernel amd-pstate-driver"
        for option in ['CONFIG_X86_AMD_PSTATE']:
            tmp = re.findall(f'{option}=y', self._config_data)
            self.assertTrue(tmp)
        for option in ['CONFIG_X86_AMD_PSTATE_DEFAULT_MODE']:
            tmp = re.findall(f'{option}=3', self._config_data)
            self.assertTrue(tmp)

    def test_inotify_stackfs(self):
        for option in ['CONFIG_INOTIFY_USER']:
            tmp = re.findall(f'{option}=y', self._config_data)
            self.assertTrue(tmp)

    def test_wwan(self):
        for option in ['CONFIG_USB_NET_DRIVERS', 'CONFIG_USB_USBNET',
                       'CONFIG_USB_NET_CDCETHER', 'CONFIG_USB_NET_HUAWEI_CDC_NCM',
                       'CONFIG_USB_NET_CDC_MBIM', 'CONFIG_USB_NET_QMI_WWAN',
                       'CONFIG_USB_SIERRA_NET', 'CONFIG_WWAN',
                       'CONFIG_USB_SERIAL', 'CONFIG_USB_SERIAL_WWAN']:
            tmp = re.findall(f'{option}=y', self._config_data)
            self.assertTrue(tmp)

        for option in ['CONFIG_WWAN_HWSIM', 'CONFIG_IOSM', 'CONFIG_MTK_T7XX']:
            tmp = re.findall(f'{option}=m', self._config_data)
            self.assertTrue(tmp)

    def test_slub(self):
        for option in ['CONFIG_SLUB_DEBUG']:
            tmp = re.findall(f'{option}=y', self._config_data)
            self.assertTrue(tmp)

    def test_kexec(self):
        for option in ['CONFIG_KEXEC', 'CONFIG_KEXEC_FILE', 'CONFIG_KEXEC_SIG']:
            tmp = re.findall(f'{option}=y', self._config_data)
            self.assertTrue(tmp)

    def test_kdump(self):
        options = [
            'CONFIG_KEXEC',
            'CONFIG_CRASH_DUMP',
            'CONFIG_DEBUG_INFO',
            'CONFIG_PROC_VMCORE',
        ]
        for option in options:
            tmp = re.findall(f'{option}=y', self._config_data)
            self.assertTrue(tmp)

    def test_openvpn_dco(self):
        options_to_check = ['CONFIG_OVPN']
        for option in options_to_check:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

    def test_wireguard(self):
        options_to_check = ['CONFIG_WIREGUARD']
        for option in options_to_check:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

    def test_vxlan(self):
        options_to_check = ['CONFIG_VXLAN']
        for option in options_to_check:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

    def test_macvlan(self):
        options_to_check = ['CONFIG_MACVLAN', 'CONFIG_MACVTAP']
        for option in options_to_check:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

    def test_dummy(self):
        options_to_check = ['CONFIG_DUMMY']
        for option in options_to_check:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

    def test_arm64(self):
        # Only required on arm64 platforms
        if not IS_ARM64:
            self.skipTest('Not an arm64 platform')

        # Marvell CN9130: CONFIG_MVPP2, CN10308
        required_options = [
            'CONFIG_MVPP2',
            'CONFIG_USB_XHCI_PLATFORM',
            'CONFIG_OCTEONTX2_AF',
            'CONFIG_OCTEONTX2_PF',
            'CONFIG_I2C_THUNDERX',
            'CONFIG_GPIO_PCA953X',
            'CONFIG_MMC_SDHCI_CADENCE',
            'CONFIG_LEDS_PCA955X_GPIO',
            'CONFIG_RTC_DRV_EFI',
            'CONFIG_RTC_DRV_PL031',
        ]

        for option in required_options:
            with self.subTest(option=option):
                tmp = re.findall(f'{option}=(y|m)', self._config_data)
                self.assertTrue(
                    tmp, msg=f'{option} must be enabled (=y or =m) on arm64'
                )

    def test_hypervisor_hyperv(self):
        if IS_ARM64:
            self.skipTest('Hyper-V only available on X86 platform')

        options_to_check = ['CONFIG_HYPERV_VSOCKETS', 'CONFIG_HYPERV_STORAGE',
                            'CONFIG_HYPERV_NET', 'CONFIG_HYPERV_KEYBOARD',
                            'CONFIG_HYPERV_TIMER', 'CONFIG_HYPERV_UTILS',
                            'CONFIG_HYPERV_BALLOON', 'CONFIG_HYPERV_VMBUS',
                            'CONFIG_HYPERV_IOMMU', 'CONFIG_PCI_HYPERV',
                            'CONFIG_PCI_HYPERV_INTERFACE']

        for option in options_to_check:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

        # T8940: a kernel built with HYPERV_VTL_MODE "must run at VTL2, and
        # will not run as a normal guest" - get_vtl() calls BUG() on every
        # regular Hyper-V VM. This option must never be enabled.
        tmp = re.findall(r'CONFIG_HYPERV_VTL_MODE=(y|m)', self._config_data)
        self.assertFalse(tmp)

    def test_hypervisor_vmware(self):
        if IS_ARM64:
            self.skipTest('VMware only available on X86 platform')

        options_to_check = ['CONFIG_VMWARE_VMCI_VSOCKETS', 'CONFIG_VMXNET3',
                            'CONFIG_VMWARE_BALLOON', 'CONFIG_VMWARE_VMCI',
                            'CONFIG_VMWARE_PVSCSI']

        for option in options_to_check:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

    def test_hypervisor_virtio(self):
        options_to_check = ['CONFIG_VIRTIO_BLK', 'CONFIG_VIRTIO_NET',
                            'CONFIG_VIRTIO_CONSOLE', 'CONFIG_VIRTIO_ANCHOR',
                            'CONFIG_VIRTIO_PCI_LIB',
                            'CONFIG_VIRTIO_PCI_LIB_LEGACY',
                            'CONFIG_VIRTIO_MENU', 'CONFIG_VIRTIO_PCI',
                            'CONFIG_VIRTIO_PCI_LEGACY', 'CONFIG_VIRTIO_VDPA',
                            'CONFIG_VIRTIO_BALLOON', 'CONFIG_VIRTIO_INPUT',
                            'CONFIG_VIRTIO_MMIO',
                            'CONFIG_VIRTIO_MMIO_CMDLINE_DEVICES',
                            'CONFIG_VIRTIO_IOMMU']

        for option in options_to_check:
            tmp = re.findall(f'{option}=(y|m)', self._config_data)
            self.assertTrue(tmp)

if __name__ == '__main__':
    unittest.main(verbosity=2)
