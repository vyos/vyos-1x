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
#
# Coverage for T3871: slot-anchored persistent interface naming.
#
# The regression classes at the bottom replay, verbatim, the field
# reproductions from the review of vyos-1x PR #5417 - the cases where the
# config-tree-driven resolver bound a configured address to the wrong
# physical wire. Under the store-based design none of them have a code path
# to travel, and these tests exist to keep it that way.

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vyos.ifconfig.ifname_store import STORE_VERSION
from vyos.ifconfig.ifname_store import canonical_sort_key
from vyos.ifconfig.ifname_store import config_dir_is_mounted
from vyos.ifconfig.ifname_store import device_matches
from vyos.ifconfig.ifname_store import ambiguous_keys
from vyos.ifconfig.ifname_store import hardware_key
from vyos.ifconfig.ifname_store import discover_devices
from vyos.ifconfig.ifname_store import empty_store
from vyos.ifconfig.ifname_store import load_store
from vyos.ifconfig.ifname_store import port_label_index
from vyos.ifconfig.ifname_store import is_vmware_nic
from vyos.ifconfig.ifname_store import _LABEL_UNKNOWN
from vyos.ifconfig.ifname_store import permanent_mac
from vyos.ifconfig.ifname_store import render_link
from vyos.ifconfig.ifname_store import resolve
from vyos.ifconfig.ifname_store import sync_link_files
from vyos.ifconfig.ifname_store import save_store


def dev(name, path, mac, wireless=False, bus='pci', label=None):
    """A device sitting at 'path'. Its key is what udev would report for it -
    here the raw ID_PATH, which is what a plain virtio or e1000e NIC with no
    firmware slot index ends up keyed on."""
    properties = {'ID_PATH': path, 'ID_BUS': bus} if path else {}
    device = {'name': name, 'mac': mac, 'wireless': wireless,
              'properties': properties,
              'key': hardware_key(properties)}
    if label is not None:
        device['label_index'] = label
    return device


def store_of(mapping, hardware=None):
    """mapping: {name: path} - the slot each name is recorded against"""
    return {
        'version': STORE_VERSION,
        'interfaces': {n: f'ID_PATH={p}' for n, p in mapping.items()},
        'hardware': dict(hardware or {}),
    }


class TestCanonicalOrder(unittest.TestCase):
    def test_pci_sorted_numerically_not_lexically(self):
        # 0000:09:00.0 must precede 0000:10:00.0 - string order gets this wrong
        a = dev('x', 'pci-0000:00:09.0', 'aa:00:00:00:00:01')
        b = dev('y', 'pci-0000:00:10.0', 'aa:00:00:00:00:02')
        self.assertLess(canonical_sort_key(a), canonical_sort_key(b))

    def test_pci_before_usb(self):
        pci = dev('x', 'pci-0000:00:1f.6', 'aa:00:00:00:00:01')
        usb = dev('y', 'usb-0:1:1.0', 'aa:00:00:00:00:00', bus='usb')
        self.assertLess(canonical_sort_key(pci), canonical_sort_key(usb))

    def test_order_is_independent_of_mac(self):
        # the whole point: a numerically higher MAC in a lower slot still wins
        low_slot = dev('x', 'pci-0000:00:02.0', 'ff:ff:ff:ff:ff:ff')
        high_slot = dev('y', 'pci-0000:00:05.0', '00:00:00:00:00:01')
        self.assertLess(canonical_sort_key(low_slot), canonical_sort_key(high_slot))


class TestHypervisorAdapterOrder(unittest.TestCase):
    """ESXi does not lay its adapters out in PCI address order. With four or
    more it puts the fourth on a root port which sorts ahead of the first
    three, so naming by PCI address alone made Network adapter 4 eth0. On the
    OVA that moves the WAN: cloud-init takes eth0 from the OVF properties.
    Reported against ESXi 8.0.3, vmx-21.
    """

    # the two interfaces from the report, verbatim
    ADAPTER_4 = ('pci-0000:04:00.0', '00:0c:29:60:0e:5c', 3)   # Ethernet3
    ADAPTER_1 = ('pci-0000:0b:00.0', '00:0c:29:60:0e:3e', 0)   # Ethernet0

    def test_the_first_adapter_sorts_first_despite_its_pci_address(self):
        a4 = dev('eth0', self.ADAPTER_4[0], self.ADAPTER_4[1], label=self.ADAPTER_4[2])
        a1 = dev('eth1', self.ADAPTER_1[0], self.ADAPTER_1[1], label=self.ADAPTER_1[2])
        self.assertEqual(sorted([a4, a1], key=canonical_sort_key)[0]['mac'],
                          self.ADAPTER_1[1])

    def test_four_adapters_are_named_in_adapter_order(self):
        devices = [dev('?', 'pci-0000:04:00.0', 'aa:03', label=3),
                   dev('?', 'pci-0000:0b:00.0', 'aa:00', label=0),
                   dev('?', 'pci-0000:0c:00.0', 'aa:01', label=1),
                   dev('?', 'pci-0000:0d:00.0', 'aa:02', label=2)]
        _, store, report = resolve(devices, empty_store())
        # assert on the hardware, not just that four names exist
        self.assertEqual(report['bootstrapped'],
                          {'eth0': 'aa:00', 'eth1': 'aa:01',
                           'eth2': 'aa:02', 'eth3': 'aa:03'})
        self.assertEqual(store['interfaces']['eth3'], 'ID_PATH=pci-0000:04:00.0')

    def test_a_labelled_and_an_unlabelled_device_can_be_compared(self):
        # the sentinel has to be an int - sort keys are tuples compared
        # element-wise, and None against int raises
        labelled = dev('eth0', 'pci-0000:0b:00.0', 'aa:00', label=0)
        plain = dev('eth1', 'pci-0000:03:00.0', 'bb:00')
        self.assertEqual(sorted([plain, labelled], key=canonical_sort_key)[0]['mac'],
                          'aa:00')

    def test_unlabelled_hardware_never_takes_the_first_name(self):
        # a passthrough NIC is not in the OVF network mapping
        devices = [dev('?', 'pci-0000:03:00.0', 'bb:00'),
                   dev('?', 'pci-0000:0b:00.0', 'aa:00', label=0)]
        _, _, report = resolve(devices, empty_store())
        self.assertEqual(report['bootstrapped']['eth0'], 'aa:00')

    def test_adding_unlabelled_hardware_does_not_reshuffle_the_adapters(self):
        adapters = [dev('?', 'pci-0000:0b:00.0', 'aa:00', label=0),
                    dev('?', 'pci-0000:04:00.0', 'aa:01', label=1)]
        plain = dev('?', 'pci-0000:03:00.0', 'bb:00')
        before = [d['mac'] for d in sorted(adapters, key=canonical_sort_key)]
        after = [d['mac'] for d in sorted(adapters + [plain], key=canonical_sort_key)]
        self.assertEqual(after[:len(before)], before)

    def test_the_order_survives_into_the_store(self):
        # the names close the gap: two adapters labelled 0 and 3 become
        # eth0 and eth1, the lowest free names in adapter order
        devices = [dev('enp4s0', 'pci-0000:04:00.0', 'aa:03', label=3),
                   dev('enp11s0', 'pci-0000:0b:00.0', 'aa:00', label=0)]
        plan, store, _ = resolve(devices, empty_store())
        self.assertEqual(plan, {'enp11s0': 'eth0', 'enp4s0': 'eth1'})

        # the next boot sees them under the names it just gave them
        for device in devices:
            device['name'] = plan[device['name']]

        plan, _, report = resolve(devices, store)
        self.assertEqual(plan, {})
        self.assertEqual(report['bootstrapped'], {})

    def test_hardware_added_later_takes_the_next_name(self):
        devices = [dev('?', 'pci-0000:0b:00.0', 'aa:00', label=0)]
        _, store, _ = resolve(devices, empty_store())
        # a second adapter, labelled lower, must not displace the first
        devices.append(dev('?', 'pci-0000:04:00.0', 'aa:09', label=9))
        _, store, report = resolve(devices, store)
        self.assertEqual(report['bootstrapped'], {'eth1': 'aa:09'})

    def test_the_label_is_ordering_only_never_identity(self):
        # it must not reach hardware_key(), or a relabelled adapter would read
        # as different hardware
        properties = {'ID_PATH': 'pci-0000:0b:00.0', 'ID_BUS': 'pci'}
        self.assertNotIn('Ethernet', hardware_key(properties))
        self.assertNotIn('label', hardware_key(properties))


def hv(name, mac):
    """A Hyper-V NIC as udev reports it on Azure: every one shares the ACPI
    VMBus node as its ID_PATH and has no slot, so its MAC is its key."""
    return {
        'name': name,
        'mac': mac,
        'wireless': False,
        'properties': {
            'ID_PATH': 'acpi-MSFT1000:00',
            'ID_NET_NAME_MAC': 'enx' + mac.replace(':', ''),
            'ID_NET_DRIVER': 'hv_netvsc',
        },
    }


def keyed(devices):
    """Keys as discover_devices() computes them, shared ID_PATH passed over"""
    ambiguous = ambiguous_keys([d['properties'] for d in devices])
    for device in devices:
        device['key'] = hardware_key(device['properties'], ambiguous)
    return devices


class TestHyperV(unittest.TestCase):
    """Azure, four NICs, measured on a fresh deployment of this series: every
    Hyper-V NIC shares one ID_PATH and has no slot, so its MAC is its key.
    The order Azure lists the NICs in is cloud-init's to record; what is left
    here is a NIC deleted and created again on the same VM, where cloud-init
    does not run again.
    """

    AZURE = [
        ('eth0', '00:0d:3a:47:38:1d'),  # WAN, the primary NIC
        ('eth1', '00:0d:3a:47:3b:29'),
        ('eth2', '00:0d:3a:47:33:ad'),
        ('eth3', '00:0d:3a:47:3b:f8'),
    ]

    def nics(self):
        return keyed([hv(name, mac) for name, mac in self.AZURE])

    def stored(self):
        """the map as cloud-init records it on Azure: the names it gave"""
        store = empty_store()
        for name, mac in self.AZURE:
            store['interfaces'][name] = 'ID_NET_NAME_MAC=enx' + mac.replace(':', '')
            store['hardware'][name] = mac
        plan, store, report = resolve(self.nics(), store)
        assert plan == {} and len(report['matched']) == 4
        return store

    def test_each_nic_is_keyed_on_its_own_mac(self):
        store = self.stored()
        self.assertEqual(
            sorted(store['interfaces'].values()),
            sorted(
                'ID_NET_NAME_MAC=enx' + mac.replace(':', '') for _, mac in self.AZURE
            ),
        )

    def test_a_recreated_nic_takes_the_name_of_the_one_it_replaced(self):
        # LAN3's NIC deleted and created again: new MAC. It came up as eth4,
        # eth3 stayed reserved and the boot commit failed on it every boot.
        store = self.stored()
        devices = self.nics()
        devices[3] = keyed([hv('eth3', '00:0d:3a:47:aa:01')] + devices[:3])[0]
        plan, store, report = resolve(devices, store)
        self.assertEqual(report.get('adopted', {}), {'eth3': '00:0d:3a:47:aa:01'})
        self.assertEqual(report['bootstrapped'], {})
        self.assertEqual(plan, {})
        self.assertEqual(store['interfaces']['eth3'], 'ID_NET_NAME_MAC=enx000d3a47aa01')

    def test_two_recreated_nics_are_not_paired_by_guess(self):
        # nothing here says which new NIC replaced which, and pairing them by
        # the order they came up in can swap two subnets' configuration
        store = self.stored()
        devices = self.nics()[:2] + keyed(
            [hv('eth3', '00:0d:3a:99:00:11'), hv('eth2', '00:0d:3a:99:00:33')]
        )
        _, store, report = resolve(devices, store)
        self.assertEqual(report.get('adopted', {}), {})
        self.assertEqual(set(report['bootstrapped']), {'eth4', 'eth5'})
        self.assertIn('eth2', store['interfaces'])
        self.assertIn('eth3', store['interfaces'])

    def test_two_vacancies_and_one_new_nic_are_not_paired(self):
        # which of two gone NICs the one new NIC replaced is not known
        store = self.stored()
        devices = self.nics()[:2] + keyed(
            [hv('eth3', '00:0d:3a:99:00:11')] + self.nics()[:2])[:1]
        _, store, report = resolve(devices, store)
        self.assertEqual(report.get('adopted', {}), {})
        self.assertEqual(report['bootstrapped'], {'eth4': '00:0d:3a:99:00:11'})
        self.assertEqual(store.get('absent'), ['eth2', 'eth3'])

    def test_a_new_nic_with_no_vacancy_takes_a_new_name(self):
        store = self.stored()
        devices = self.nics() + keyed([hv('eth4', '00:0d:3a:48:00:09')])
        _, _, report = resolve(devices, store)
        self.assertEqual(report.get('adopted', {}), {})
        self.assertEqual(report['bootstrapped'], {'eth4': '00:0d:3a:48:00:09'})

    def test_one_vacancy_and_two_new_nics_are_not_paired(self):
        store = self.stored()
        devices = self.nics()[:3] + keyed(
            [hv('eth3', '00:0d:3a:48:00:01'), hv('eth4', '00:0d:3a:48:00:02')]
        )
        _, _, report = resolve(devices, store)
        self.assertEqual(report.get('adopted', {}), {})

    def test_a_disk_on_all_new_nics_is_not_handed_over_here(self):
        # every recorded NIC gone at once: the platform's order is cloud-init's
        # to supply (it runs again on a new instance); guessing it here could
        # put the WAN's configuration on a LAN
        store = self.stored()
        new = keyed([hv(f'eth{i}', f'00:0d:3a:48:00:0{i}') for i in range(4)])
        _, _, report = resolve(new, store)
        self.assertEqual(report.get('adopted', {}), {})

    def test_a_slot_keyed_name_is_never_adopted(self):
        # a PCI card has a slot to come back to; its name stays reserved
        devices = [dev('eth0', 'pci-0000:00:03.0', 'aa:00')]
        _, store, _ = resolve(devices, empty_store())
        other = keyed([hv('eth1', '00:0d:3a:48:00:09')])
        _, store, report = resolve(other, store)
        self.assertEqual(report.get('adopted', {}), {})
        self.assertEqual(report['bootstrapped'], {'eth1': '00:0d:3a:48:00:09'})

    def test_a_nic_added_after_one_was_removed_is_not_its_replacement(self):
        # P8, measured on Azure: LAN3's NIC deleted for good (one boot), a NIC
        # on another subnet added later (the next boot). Taking the vacant
        # name put LAN3's configuration on the other subnet.
        store = self.stored()
        devices = self.nics()[:3]
        _, store, report = resolve(devices, store)
        self.assertEqual(report.get('adopted', {}), {})
        later = devices + keyed([hv('eth4', '38:33:c5:cc:a3:3e')])
        _, store, report = resolve(later, store)
        self.assertEqual(report.get('adopted', {}), {})
        self.assertEqual(report['bootstrapped'], {'eth4': '38:33:c5:cc:a3:3e'})
        self.assertEqual(store.get('absent'), ['eth3'])

    def test_a_nic_replaced_on_a_running_system_is_not_adopted(self):
        # measured on Hyper-V: a NIC hot-added after another was hot-removed
        # took its name at once, while the configuration under that name
        # stayed unapplied until the next boot
        store = self.stored()
        devices = self.nics()
        devices[3] = keyed([hv('eth3', '00:0d:3a:47:aa:01')] + devices[:3])[0]
        _, store, report = resolve(devices, store, adopt=False)
        self.assertEqual(report.get('adopted', {}), {})
        self.assertEqual(report['bootstrapped'], {'eth4': '00:0d:3a:47:aa:01'})
        self.assertEqual(store.get('absent'), ['eth3'])
        # nor at the next boot: the name was already missing at the last pass
        _, store, report = resolve(devices, store)
        self.assertEqual(report.get('adopted', {}), {})
        self.assertEqual(report['matched'].get('eth4'), '00:0d:3a:47:aa:01')

    def test_a_name_whose_nic_was_not_hyperv_is_not_handed_over(self):
        # a MAC-keyed name can belong to other hardware sharing the VMBus
        # path; only a Hyper-V NIC's name goes to a Hyper-V replacement
        other = hv('eth1', '00:0d:3a:47:3b:29')
        other['properties']['ID_NET_DRIVER'] = 'mlx5_core'
        devices = keyed([hv('eth0', '00:0d:3a:47:38:1d'), other])
        _, store, _ = resolve(devices, empty_store())
        self.assertEqual(store.get('hyperv'), ['eth0'])
        later = keyed([hv('eth0', '00:0d:3a:47:38:1d'),
                       hv('eth1', '00:0d:3a:48:00:09')])
        _, _, report = resolve(later, store)
        self.assertEqual(report.get('adopted', {}), {})
        self.assertEqual(report['bootstrapped'], {'eth2': '00:0d:3a:48:00:09'})

    def test_only_a_hyperv_nic_takes_a_vacant_name(self):
        store = self.stored()
        new = hv('eth3', '00:0d:3a:48:00:09')
        new['properties']['ID_NET_DRIVER'] = 'virtio_net'
        devices = self.nics()[:3] + keyed([new] + self.nics()[:3])[:1]
        _, _, report = resolve(devices, store)
        self.assertEqual(report.get('adopted', {}), {})
        self.assertEqual(report['bootstrapped'], {'eth4': '00:0d:3a:48:00:09'})

    def test_a_new_nic_takes_no_name_of_another_namespace(self):
        store = self.stored()
        new = keyed([hv('wlan0', '00:0d:3a:48:00:09')] + self.nics()[:3])[0]
        new['wireless'] = True
        _, _, report = resolve(self.nics()[:3] + [new], store)
        self.assertEqual(report.get('adopted', {}), {})
        self.assertEqual(report['bootstrapped'], {'wlan0': '00:0d:3a:48:00:09'})

    def test_a_store_that_does_not_say_which_nics_were_hyperv_hands_nothing_over(self):
        # written by code that did not record it: whether the vacant name
        # was a Hyper-V NIC's, or how long it has been vacant, is unknown
        store = self.stored()
        store.pop('hyperv')
        devices = self.nics()
        devices[3] = keyed([hv('eth3', '00:0d:3a:47:aa:01')] + devices[:3])[0]
        _, store, report = resolve(devices, store)
        self.assertEqual(report.get('adopted', {}), {})
        self.assertEqual(report['bootstrapped'], {'eth4': '00:0d:3a:47:aa:01'})
        self.assertEqual(store.get('absent'), ['eth3'])

    def test_the_hyperv_record_survives_a_load_and_follows_the_nics(self):
        store = self.stored()
        self.assertEqual(store['hyperv'], ['eth0', 'eth1', 'eth2', 'eth3'])
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'map.json'
            with mock.patch('vyos.ifconfig.ifname_store.config_dir_is_mounted',
                            return_value=True), \
                 mock.patch('vyos.ifconfig.ifname_store.get_cfg_group_id',
                            return_value=0):
                save_store(store, path)
            self.assertEqual(load_store(path)['hyperv'], store['hyperv'])
        # an absent NIC keeps its record, so its replacement is recognised
        _, store, _ = resolve(self.nics()[:3], store)
        self.assertEqual(store['hyperv'], ['eth0', 'eth1', 'eth2', 'eth3'])

    def test_a_lone_hyperv_nic_keyed_on_its_path_still_pins_its_driver(self):
        # one NIC has the VMBus path to itself, so it is keyed on it; its VF
        # must not match its file any more than with a MAC key
        devices = keyed([hv('eth0', '00:0d:3a:47:38:1d')])
        _, store, _ = resolve(devices, empty_store())
        self.assertTrue(store['interfaces']['eth0'].startswith('ID_PATH='))
        with tempfile.TemporaryDirectory() as d:
            sync_link_files(store, link_dir=Path(d), devices=devices)
            body = (Path(d) / '10-vyos-eth0.link').read_text()
        self.assertIn('Driver=hv_netvsc\n', body)

    def test_a_store_without_the_record_still_adopts(self):
        # written before names missing at a pass were recorded: nothing was
        # missing then, as far as it can say, so a one-step replacement holds
        store = self.stored()
        store.pop('absent', None)
        devices = self.nics()
        devices[3] = keyed([hv('eth3', '00:0d:3a:47:aa:01')] + devices[:3])[0]
        _, _, report = resolve(devices, store)
        self.assertEqual(report.get('adopted', {}), {'eth3': '00:0d:3a:47:aa:01'})

    def test_the_record_clears_when_the_nic_is_back(self):
        store = self.stored()
        _, store, _ = resolve(self.nics()[:3], store)
        self.assertEqual(store.get('absent'), ['eth3'])
        _, store, report = resolve(self.nics(), store)
        self.assertNotIn('absent', store)
        self.assertEqual(report['matched']['eth3'], self.AZURE[3][1])

    def test_the_record_survives_a_load(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        path = tmp / 'interface-mapping.json'
        store = self.stored()
        _, store, _ = resolve(self.nics()[:3], store)
        path.write_text(json.dumps(store))
        self.assertEqual(load_store(path).get('absent'), ['eth3'])
        # a name the map no longer has is dropped from it
        store['absent'] = ['eth3', 'eth9']
        path.write_text(json.dumps(store))
        self.assertEqual(load_store(path).get('absent'), ['eth3'])

    def test_link_file_pins_the_driver_for_a_mac_key(self):
        # the accelerated-networking VF carries its NIC's MAC
        body = render_link('eth0', 'ID_NET_NAME_MAC=enx000d3a47381d', 'hv_netvsc')
        self.assertIn(
            'Property=ID_NET_NAME_MAC=enx000d3a47381d\nDriver=hv_netvsc\n', body
        )

    def test_link_file_without_a_driver_is_unchanged(self):
        self.assertNotIn('Driver=', render_link('eth0', 'ID_PATH=pci-0000:00:03.0'))

    def link_dir(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        return tmp

    def test_sync_pins_the_driver_for_hyperv_only(self):
        devices = self.nics()
        usb = {
            'name': 'eth4',
            'mac': 'aa:00:00:00:00:04',
            'wireless': False,
            'properties': {
                'ID_NET_NAME_MAC': 'enxaa0000000004',
                'ID_NET_DRIVER': 'r8152',
            },
        }
        devices += keyed([usb])
        _, store, _ = resolve(devices, empty_store())
        tmp = self.link_dir()
        sync_link_files(store, link_dir=tmp, devices=devices)
        name_of = {key: name for name, key in store['interfaces'].items()}
        wan = name_of['ID_NET_NAME_MAC=enx000d3a47381d']
        other = name_of['ID_NET_NAME_MAC=enxaa0000000004']
        self.assertIn('Driver=hv_netvsc', (tmp / f'10-vyos-{wan}.link').read_text())
        self.assertNotIn('Driver=', (tmp / f'10-vyos-{other}.link').read_text())

    def test_an_absent_nic_keeps_its_driver_pin(self):
        # a boot without the NIC used to rewrite its file without the pin, and
        # on its return its VF matched the file again
        devices = self.nics()
        _, store, _ = resolve(devices, empty_store())
        tmp = self.link_dir()
        sync_link_files(store, link_dir=tmp, devices=devices)
        sync_link_files(store, link_dir=tmp, devices=devices[:3])
        self.assertIn('Driver=hv_netvsc', (tmp / '10-vyos-eth3.link').read_text())


class TestReplacedHardware(unittest.TestCase):
    """A slot keeps its name when its card is swapped - which hands that
    interface's addresses to different hardware. resolve() reports the change
    so vyos-router can warn instead of letting it happen silently.
    """

    PATH = 'pci-0000:00:12.0'

    def _device(self, mac):
        return dev('eth0', self.PATH, mac)

    def test_same_card_reports_nothing(self):
        store = store_of({'eth0': self.PATH}, {'eth0': 'aa:aa:aa:aa:aa:01'})
        _, _, report = resolve([self._device('aa:aa:aa:aa:aa:01')], store)
        self.assertEqual(report['replaced'], {})

    def test_swapped_card_is_reported_with_its_new_mac(self):
        store = store_of({'eth0': self.PATH}, {'eth0': 'aa:aa:aa:aa:aa:01'})
        _, new_store, report = resolve([self._device('bb:bb:bb:bb:bb:02')], store)
        self.assertEqual(report['replaced'], {'eth0': 'bb:bb:bb:bb:bb:02'})
        # the name is still the slot's, and the new card is now what is on record
        self.assertEqual(new_store['interfaces']['eth0'], f'ID_PATH={self.PATH}')
        self.assertEqual(new_store['hardware']['eth0'], 'bb:bb:bb:bb:bb:02')

    def test_reported_once_not_on_every_later_boot(self):
        store = store_of({'eth0': self.PATH}, {'eth0': 'aa:aa:aa:aa:aa:01'})
        _, store, _ = resolve([self._device('bb:bb:bb:bb:bb:02')], store)
        _, _, report = resolve([self._device('bb:bb:bb:bb:bb:02')], store)
        self.assertEqual(report['replaced'], {})

    def test_absent_card_keeps_its_record_so_a_later_swap_is_caught(self):
        store = store_of({'eth0': self.PATH}, {'eth0': 'aa:aa:aa:aa:aa:01'})
        _, store, _ = resolve([], store)
        self.assertEqual(store['hardware']['eth0'], 'aa:aa:aa:aa:aa:01')
        _, _, report = resolve([self._device('bb:bb:bb:bb:bb:02')], store)
        self.assertEqual(report['replaced'], {'eth0': 'bb:bb:bb:bb:bb:02'})

    def test_new_hardware_is_not_a_replacement(self):
        _, _, report = resolve([self._device('aa:aa:aa:aa:aa:01')], empty_store())
        self.assertEqual(report['replaced'], {})
        self.assertIn('eth0', report['bootstrapped'])

    def test_store_written_before_this_field_reports_nothing(self):
        # nothing to compare against yet - and no interface may be renamed
        legacy = {'version': STORE_VERSION,
                  'interfaces': {'eth0': f'ID_PATH={self.PATH}'}}
        plan, new_store, report = resolve([self._device('aa:aa:aa:aa:aa:01')],
                                           legacy)
        self.assertEqual(report['replaced'], {})
        self.assertEqual(plan, {})
        self.assertEqual(new_store['interfaces']['eth0'], f'ID_PATH={self.PATH}')


class TestMovedHardware(unittest.TestCase):
    """A card carries its name with it. Matching on the slot alone would give
    the name - and the address configured under it - to whatever took the old
    position, which is how a card added for another purpose ended up on
    another segment's address.
    """

    A = 'aa:aa:aa:aa:aa:01'
    B = 'bb:bb:bb:bb:bb:02'
    C = 'cc:cc:cc:cc:cc:03'

    def setUp(self):
        self.store = store_of({'eth0': 'pci-0000:00:02.0',
                               'eth1': 'pci-0000:00:03.0'},
                              {'eth0': self.A, 'eth1': self.B})

    @staticmethod
    def _at(slot, mac):
        return dev('?', f'pci-0000:00:{slot:02x}.0', mac)

    def test_card_moved_to_another_slot_keeps_its_name(self):
        _, store, report = resolve([self._at(4, self.A), self._at(3, self.B)],
                                    self.store)
        self.assertEqual(report['moved'], {'eth0': self.A})
        self.assertEqual(report['replaced'], {})
        self.assertEqual(store['interfaces']['eth0'], 'ID_PATH=pci-0000:00:04.0')

    def test_a_new_card_in_the_vacated_slot_does_not_inherit_the_name(self):
        # the shape reported from the field, with the original card still in
        # the box: it keeps eth0, and the newcomer is named as new hardware
        _, store, report = resolve(
            [self._at(4, self.A), self._at(3, self.B), self._at(2, self.C)],
            self.store)
        self.assertEqual(report['moved'], {'eth0': self.A})
        self.assertEqual(report['bootstrapped'], {'eth2': self.C})
        self.assertEqual(report['replaced'], {})
        self.assertEqual(store['interfaces']['eth0'], 'ID_PATH=pci-0000:00:04.0')

    def test_two_known_cards_swapping_slots_stay_with_their_slots(self):
        # Both cards are on record, so this is a rearrangement within the set
        # the store already describes - and the store is what decides names.
        # The same path covers an operator swapping two entries by hand, which
        # has to take effect or the map would not be authoritative at all.
        _, store, report = resolve([self._at(3, self.A), self._at(2, self.B)],
                                    self.store)
        self.assertEqual(report['moved'], {})
        self.assertEqual(report['matched'], {})
        self.assertEqual(report['reassigned'], {'eth0': self.B, 'eth1': self.A})
        self.assertEqual(store['interfaces']['eth0'], 'ID_PATH=pci-0000:00:02.0')
        self.assertEqual(store['hardware']['eth0'], self.B)

    def test_editing_the_slot_map_by_hand_takes_effect(self):
        # what `make test-interface-naming` does: swap the two entries in 'interfaces'
        # and leave 'hardware' alone. Following the recorded address here
        # would quietly undo the edit.
        store = store_of({'eth0': 'pci-0000:00:03.0',
                          'eth1': 'pci-0000:00:02.0'},
                         {'eth0': self.A, 'eth1': self.B})
        _, _, report = resolve([self._at(2, self.A), self._at(3, self.B)],
                                store)
        self.assertEqual(report['matched'], {})
        self.assertEqual(report['reassigned'], {'eth0': self.B, 'eth1': self.A})
        self.assertEqual(report['moved'], {})

    def test_identity_wins_over_the_slot(self):
        # both rules could fire: the card that owns the name sits elsewhere
        # while another card occupies its recorded slot. The card wins.
        _, _, report = resolve(
            [self._at(4, self.A), self._at(2, self.C), self._at(3, self.B)],
            self.store)
        self.assertIn('eth0', report['moved'])
        self.assertNotIn('eth0', report['replaced'])

    def test_gone_card_still_falls_back_to_the_slot_and_is_reported(self):
        # the original is nowhere to be found, so nothing distinguishes an
        # in-place replacement from an unrelated card - the slot decides, loudly
        _, _, report = resolve([self._at(2, self.C), self._at(3, self.B)],
                                self.store)
        self.assertEqual(report['replaced'], {'eth0': self.C})
        self.assertEqual(report['moved'], {})


class TestWwanNaming(unittest.TestCase):
    """A modem is addressed as wwanN by the CLI - 'interfaces wwan' looks at
    nothing else. Naming it ethN like any other port left an HP lt4132 bound,
    working and completely invisible on a DUT.
    """

    WWP = 'wwp0s20f0u2u4c3'
    MODEM_MAC = 'b6:53:dd:66:c2:98'

    def _modem(self, name='eth6'):
        # no address: discovery keeps none for a modem
        properties = {'ID_NET_NAME_PATH': self.WWP, 'ID_BUS': 'usb'}
        return {'name': name, 'mac': '', 'wireless': False,
                'wwan': True, 'properties': properties,
                'key': f'ID_NET_NAME_PATH={self.WWP}'}

    def _nic(self, name='eth0', path='enp3s0', mac='00:f0:cb:fe:ba:99'):
        properties = {'ID_NET_NAME_PATH': path, 'ID_BUS': 'pci'}
        return {'name': name, 'mac': mac, 'wireless': False, 'wwan': False,
                'properties': properties, 'key': f'ID_NET_NAME_PATH={path}'}

    def test_a_modem_is_named_in_its_own_namespace(self):
        _, store, _ = resolve([self._nic(), self._modem()], empty_store())
        self.assertEqual(store['interfaces']['wwan0'],
                          f'ID_NET_NAME_PATH={self.WWP}')
        # and it must not have eaten an ethernet number on the way
        self.assertEqual(store['interfaces']['eth0'],
                          'ID_NET_NAME_PATH=enp3s0')
        self.assertNotIn('eth1', store['interfaces'])

    def test_the_link_file_names_the_type_the_device_is(self):
        # a .link naming a type the device is not simply never applies
        body = render_link('wwan0', f'ID_NET_NAME_PATH={self.WWP}')
        self.assertIn('Type=wwan', body)
        self.assertNotIn('Type=ether', body)

    def test_a_modem_filed_under_an_ethernet_name_is_reclaimed(self):
        # what an earlier version left on the DUT: the entry still matches the
        # modem by path, so without dropping it the modem is captured again and
        # stays invisible to 'interfaces wwan'
        store = {'version': STORE_VERSION,
                 'interfaces': {'eth0': 'ID_NET_NAME_PATH=enp3s0',
                                'eth6': f'ID_NET_NAME_PATH={self.WWP}'},
                 'hardware': {'eth0': '00:f0:cb:fe:ba:99',
                              'eth6': self.MODEM_MAC}}
        plan, new_store, _ = resolve([self._nic(), self._modem()], store)

        self.assertNotIn('eth6', new_store['interfaces'])
        self.assertNotIn('eth6', new_store['hardware'])
        self.assertEqual(new_store['interfaces']['wwan0'],
                          f'ID_NET_NAME_PATH={self.WWP}')
        self.assertEqual(plan, {'eth6': 'wwan0'})

    def test_the_stale_link_file_goes_with_it(self):
        store = {'version': STORE_VERSION,
                 'interfaces': {'eth6': f'ID_NET_NAME_PATH={self.WWP}'},
                 'hardware': {'eth6': self.MODEM_MAC}}
        _, new_store, _ = resolve([self._modem()], store)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / '10-vyos-eth6.link').write_text('left over')
            sync_link_files(new_store, Path(d))
            names = sorted(p.name for p in Path(d).iterdir())
        self.assertEqual(names, ['10-vyos-wwan0.link'])

    def test_a_nic_in_the_modem_s_socket_does_not_take_its_name(self):
        # the modem is gone and an ordinary USB NIC is in the port it used.
        # The slot matches, but wwan0 is a name 'interfaces wwan' reads - give
        # it to a NIC and the modem's configuration is applied to a card that
        # cannot carry it. Leave the name reserved and name the NIC as a NIC.
        store = {'version': STORE_VERSION,
                 'interfaces': {'wwan0': f'ID_NET_NAME_PATH={self.WWP}'},
                 'hardware': {}}
        nic = self._nic('eth0', self.WWP, 'aa:bb:cc:dd:ee:07')
        _, new_store, report = resolve([nic], store)

        self.assertEqual(report['replaced'], {})
        self.assertIn('eth0', new_store['interfaces'])
        self.assertEqual(new_store['interfaces']['wwan0'],
                          f'ID_NET_NAME_PATH={self.WWP}')

    def test_a_modem_is_not_reported_as_replaced(self):
        # its address changes at every probe, so comparing it reported the
        # modem as a different card in the same socket on every boot
        store = {'version': STORE_VERSION,
                 'interfaces': {'wwan0': f'ID_NET_NAME_PATH={self.WWP}'},
                 'hardware': {'wwan0': self.MODEM_MAC}}
        plan, new_store, report = resolve([self._modem('wwan0')], store)

        self.assertEqual(plan, {})
        self.assertEqual(report['replaced'], {})
        self.assertIn('wwan0', report['matched'])
        # and an address an earlier version recorded is dropped, so a store
        # already carrying one settles on the next pass
        self.assertNotIn('wwan0', new_store['hardware'])

    def test_a_card_whose_address_changed_is_still_replaced(self):
        # the modem must not have weakened this: a card in a recorded slot
        # with a different address is the case worth warning about
        store = {'version': STORE_VERSION,
                 'interfaces': {'eth0': 'ID_NET_NAME_PATH=enp3s0'},
                 'hardware': {'eth0': '00:f0:cb:fe:ba:99'}}
        nic = self._nic('eth0', 'enp3s0', 'aa:bb:cc:dd:ee:07')
        _, _, report = resolve([nic], store)

        self.assertIn('eth0', report['replaced'])

    def test_an_ordinary_port_on_the_usb_bus_is_not_a_modem(self):
        # the key alone cannot tell them apart - a device falling back to
        # ID_PATH reads usb-... whether it is a modem or not
        usb_nic = self._nic('eth1', 'enp0s20f0u3', 'aa:bb:cc:dd:ee:01')
        usb_nic['properties'] = {'ID_PATH': 'usb-0:2:1.0', 'ID_BUS': 'usb'}
        usb_nic['key'] = 'ID_PATH=usb-0:2:1.0'
        _, store, _ = resolve([usb_nic], empty_store())
        self.assertIn('eth0', store['interfaces'])
        self.assertNotIn('wwan0', store['interfaces'])


class TestStoreIO(unittest.TestCase):
    @staticmethod
    def _config_dir(d):
        """An ordinary, unencrypted config directory - the common case."""
        return Path(d) / 'interface-mapping.json'

    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d, \
             mock.patch('vyos.ifconfig.ifname_store.encrypted_config_volume',
                        return_value=False):
            p = self._config_dir(d)
            s = store_of({'eth0': 'pci-0000:00:12.0'})
            self.assertTrue(save_store(s, p))
            self.assertEqual(load_store(p), s)

    def test_refuses_to_write_when_the_encrypted_volume_is_not_mounted(self):
        # TPM/LUKS unlock failed: vyos-router continues, but persisting here
        # would write a shadow store that the real volume masks later
        with tempfile.TemporaryDirectory() as d, \
             mock.patch('vyos.ifconfig.ifname_store.encrypted_config_volume',
                        return_value=True):
            p = Path(d) / 'interface-mapping.json'   # a plain dir, not a mount
            self.assertFalse(save_store(store_of({'eth0': 'x'}), p))
            self.assertFalse(p.exists())

    def test_writes_on_the_first_boot_of_a_prebuilt_image(self):
        # T3871: the check used to key on '.vyatta_config', which an
        # activation script writes only AFTER interface naming has run. On a
        # qcow2 that marker is absent on the first boot, so no store was ever
        # written and the next boot named the hardware from scratch - pull a
        # card and every name below it moved onto the wrong port.
        with tempfile.TemporaryDirectory() as d, \
             mock.patch('vyos.ifconfig.ifname_store.encrypted_config_volume',
                        return_value=False):
            p = Path(d) / 'interface-mapping.json'
            self.assertFalse((Path(d) / '.vyatta_config').exists())
            self.assertTrue(save_store(store_of({'eth0': 'pci-0000:00:12.0'}), p))
            self.assertTrue(p.exists())

    def test_unencrypted_config_needs_no_mount_point(self):
        # the config directory of an ordinary install is not a mount of its
        # own - only an encrypted one is
        with tempfile.TemporaryDirectory() as d, \
             mock.patch('vyos.ifconfig.ifname_store.encrypted_config_volume',
                        return_value=False):
            self.assertTrue(config_dir_is_mounted(
                Path(d) / 'interface-mapping.json'))

    def test_missing_file_is_empty_store(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(load_store(Path(d) / 'nope.json'), empty_store())

    def test_corrupt_file_is_empty_store(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._config_dir(d)
            p.write_text('{ this is not json')
            self.assertEqual(load_store(p), empty_store())

    def test_write_is_atomic_no_leftovers(self):
        with tempfile.TemporaryDirectory() as d, \
             mock.patch('vyos.ifconfig.ifname_store.encrypted_config_volume',
                        return_value=False):
            p = self._config_dir(d)
            save_store(store_of({'eth0': 'pci-0000:00:12.0'}), p)
            self.assertEqual(sorted(f.name for f in Path(d).iterdir()),
                             ['interface-mapping.json'])


def final_names(report):
    """Which name each MAC ended up with, read back off the resolve report."""
    out = {}
    for bucket in report.values():
        for name, mac in bucket.items():
            out[mac] = name
    return out


class TestDeviceMatches(unittest.TestCase):
    """A stored key names the property it was taken from, so matching a
    device is comparing that one property - never a guess about which
    identifier was meant."""

    def test_matches_the_named_property(self):
        self.assertTrue(device_matches({'ID_NET_NAME_SLOT': 'ens18'},
                                       'ID_NET_NAME_SLOT=ens18'))

    def test_same_value_under_a_different_property_does_not_match(self):
        self.assertFalse(device_matches({'ID_NET_NAME_PATH': 'ens18'},
                                        'ID_NET_NAME_SLOT=ens18'))

    def test_device_without_the_property_does_not_match(self):
        self.assertFalse(device_matches({'ID_PATH': 'pci-0000:00:12.0'},
                                        'ID_NET_NAME_SLOT=ens18'))

    def test_empty_or_malformed_key_never_matches(self):
        self.assertFalse(device_matches({'ID_NET_NAME_SLOT': 'ens18'}, ''))
        self.assertFalse(device_matches({'ID_NET_NAME_SLOT': 'ens18'}, 'ens18'))


class TestResolveBasics(unittest.TestCase):
    def test_first_boot_bootstraps_in_slot_order(self):
        devices = [
            dev('eth0', 'pci-0000:00:15.0', '00:00:5e:00:53:03'),
            dev('eth1', 'pci-0000:00:12.0', '00:00:5e:00:53:00'),
            dev('eth2', 'pci-0000:00:13.0', '00:00:5e:00:53:01'),
        ]
        _, new_store, _ = resolve(devices, empty_store())
        self.assertEqual(new_store['interfaces']['eth0'], 'ID_PATH=pci-0000:00:12.0')
        self.assertEqual(new_store['interfaces']['eth1'], 'ID_PATH=pci-0000:00:13.0')
        self.assertEqual(new_store['interfaces']['eth2'], 'ID_PATH=pci-0000:00:15.0')

    def test_established_names_are_stable_regardless_of_probe_order(self):
        store = store_of({'eth0': 'pci-0000:00:12.0', 'eth1': 'pci-0000:00:13.0'})
        # drivers finished in the opposite order this boot
        devices = [
            dev('eth0', 'pci-0000:00:13.0', '00:00:5e:00:53:01'),
            dev('eth1', 'pci-0000:00:12.0', '00:00:5e:00:53:00'),
        ]
        plan, _, _ = resolve(devices, store)
        self.assertEqual(plan, {'eth0': 'eth1', 'eth1': 'eth0'})

    def test_replacement_nic_in_same_slot_inherits_name(self):
        # the slot is the identity, so this needs no special rule: whatever
        # card is in eth1's slot is eth1, along with its configuration
        store = store_of({'eth1': 'pci-0000:00:13.0'})
        devices = [dev('eth0', 'pci-0000:00:13.0', 'bb:bb:bb:bb:bb:bb')]
        plan, new_store, report = resolve(devices, store)
        self.assertEqual(plan, {'eth0': 'eth1'})
        self.assertEqual(report['matched'], {'eth1': 'bb:bb:bb:bb:bb:bb'})
        self.assertEqual(new_store['interfaces']['eth1'], 'ID_PATH=pci-0000:00:13.0')

    def test_a_card_moved_to_another_slot_takes_that_slot_s_name(self):
        # the consequence of slot identity, stated plainly: move a card and it
        # becomes whatever the new slot is called, not what it used to be
        store = store_of({'eth1': 'pci-0000:00:13.0', 'eth2': 'pci-0000:00:14.0'})
        devices = [dev('eth9', 'pci-0000:00:14.0', 'aa:aa:aa:aa:aa:aa')]
        plan, _, report = resolve(devices, store)
        self.assertEqual(plan, {'eth9': 'eth2'})
        self.assertEqual(final_names(report)['aa:aa:aa:aa:aa:aa'], 'eth2')

    def test_absent_hardware_keeps_its_name_reserved(self):
        store = store_of({'eth0': 'pci-0000:00:12.0', 'eth1': 'pci-0000:00:13.0'})
        # eth0's slot is empty; a brand new card appeared elsewhere
        devices = [
            dev('eth0', 'pci-0000:00:13.0', '00:00:5e:00:53:01'),
            dev('eth1', 'pci-0000:00:1c.0', 'cc:cc:cc:cc:cc:cc'),
        ]
        _, new_store, report = resolve(devices, store)
        # the new card must not inherit eth0's name, and with it eth0's config
        self.assertNotEqual(final_names(report)['cc:cc:cc:cc:cc:cc'], 'eth0')
        self.assertEqual(new_store['interfaces']['eth0'], 'ID_PATH=pci-0000:00:12.0')

    def test_hardware_with_no_usable_path_falls_back_to_its_mac(self):
        # some paravirtual buses give udev nothing to build a path from; the
        # MAC-derived name is the last step of the key chain so the interface
        # is still stable instead of being renamed every boot
        properties = {'ID_NET_NAME_MAC': 'enxaabbccddeeff'}
        device = {'name': 'eth0', 'mac': 'aa:bb:cc:dd:ee:ff', 'wireless': False,
                  'properties': properties, 'key': hardware_key(properties)}
        _, new_store, _ = resolve([device], empty_store())
        self.assertEqual(new_store['interfaces']['eth0'],
                         'ID_NET_NAME_MAC=enxaabbccddeeff')

    def test_a_path_two_devices_share_is_not_used_to_identify_either(self):
        # a modem can put several interfaces on one parent device, and they
        # then report the same path. Keying both on it would give them one
        # name between them, so fall through to something which tells them
        # apart.
        first = {'ID_PATH': 'pci-0000:00:12.0',
                 'ID_NET_NAME_MAC': 'enxaabbccddee01'}
        second = {'ID_PATH': 'pci-0000:00:12.0',
                  'ID_NET_NAME_MAC': 'enxaabbccddee02'}
        ambiguous = ambiguous_keys([first, second])
        self.assertEqual(hardware_key(first, ambiguous),
                         'ID_NET_NAME_MAC=enxaabbccddee01')
        self.assertEqual(hardware_key(second, ambiguous),
                         'ID_NET_NAME_MAC=enxaabbccddee02')

    def test_a_path_only_one_device_has_is_still_used(self):
        first = {'ID_PATH': 'pci-0000:00:12.0'}
        second = {'ID_PATH': 'pci-0000:00:13.0'}
        ambiguous = ambiguous_keys([first, second])
        self.assertEqual(hardware_key(first, ambiguous),
                         'ID_PATH=pci-0000:00:12.0')

    def test_firmware_slot_is_preferred_over_a_bare_pci_path(self):
        # a firmware slot index survives PCI renumbering, a bus address does not
        properties = {'ID_NET_NAME_SLOT': 'ens18',
                      'ID_NET_NAME_PATH': 'enp0s18',
                      'ID_PATH': 'pci-0000:00:12.0'}
        self.assertEqual(hardware_key(properties), 'ID_NET_NAME_SLOT=ens18')

    def test_a_radio_recorded_by_an_older_version_is_dropped(self):
        # Wireless is no longer named here: every interface on a phy carries
        # that phy's address, so an entry recorded against one of them would
        # be applied to whichever appeared next - renaming an interface the
        # operator had just created by name. Drop what an older version wrote
        # so the entry, and the .link file made from it, go away on upgrade.
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'interface-mapping.json'
            p.write_text(json.dumps({
                'version': STORE_VERSION,
                'interfaces': {'eth0': 'ID_PATH=pci-0000:00:12.0',
                               'wlan0': 'ID_NET_NAME_MAC=wlx020000000000'},
                'hardware': {'eth0': 'aa:aa:aa:aa:aa:aa',
                             'wlan0': '02:00:00:00:00:00'}}))
            store = load_store(p)
        self.assertEqual(list(store['interfaces']), ['eth0'])
        self.assertNotIn('wlan0', store['hardware'])


class TestPR5417Regressions(unittest.TestCase):
    """Each test replays a reproduction from the review of PR #5417, where the
    config-tree-driven resolver put a configured address on the wrong wire.
    The assertions are about physical correctness - which MAC ends up behind
    which name - not about log output.
    """

    def test_multi_nic_cloud_init_first_boot(self):
        """2026-08-25 #1: three NICs, cloud-init synthesized a hw-id for eth0
        only. eth1/eth2 were pushed to eth3/eth4 and both data addresses were
        unreachable, persisting across reboot.
        """
        devices = [
            dev('eth0', 'pci-0000:00:03.0', '52:54:00:00:00:10'),
            dev('eth1', 'pci-0000:00:04.0', '52:54:00:ff:00:21'),
            dev('eth2', 'pci-0000:00:05.0', '52:54:00:00:00:22'),
        ]
        _, new_store, report = resolve(devices, empty_store())
        names = final_names(report)
        self.assertEqual(names['52:54:00:00:00:10'], 'eth0')
        self.assertEqual(names['52:54:00:ff:00:21'], 'eth1')
        self.assertEqual(names['52:54:00:00:00:22'], 'eth2')
        self.assertEqual(set(new_store['interfaces']), {'eth0', 'eth1', 'eth2'})

    def test_names_follow_slots_not_mac_magnitude(self):
        """2026-08-25 #2: the resolver swapped eth1/eth2 by MAC order, so each
        address landed on the other's physical network, and the swap was
        persisted with no warning. eth1 sits in the lower slot but has the
        numerically HIGHER MAC.
        """
        devices = [
            dev('eth1', 'pci-0000:00:04.0', '52:54:00:ff:00:21'),
            dev('eth2', 'pci-0000:00:05.0', '52:54:00:00:00:22'),
        ]
        _, _, report = resolve(devices, empty_store())
        names = final_names(report)
        self.assertEqual(names['52:54:00:ff:00:21'], 'eth0')
        self.assertEqual(names['52:54:00:00:00:22'], 'eth1')

    def test_box_named_out_of_slot_order_is_not_reordered(self):
        """2026-09-02 / 2026-09-09: a box first named by an earlier release in
        MAC order - eth1 on the slot-5 NIC, eth4 on the slot-2 NIC. Deleting
        hw-id entries made the resolver re-derive names in PCI slot order and
        put eth1 and eth4 on each other's cable, silently and permanently.

        The store records the slot each name was actually on, so nothing is
        ever re-derived and the box keeps the names it had.
        """
        store = store_of({
            'eth0': 'pci-0000:00:01.0',
            'eth1': 'pci-0000:00:05.0',
            'eth2': 'pci-0000:00:03.0',
            'eth3': 'pci-0000:00:04.0',
            'eth4': 'pci-0000:00:02.0',
        })
        devices = [
            dev('eth0', 'pci-0000:00:01.0', '00:00:5e:00:54:01'),
            dev('eth1', 'pci-0000:00:05.0', '00:00:5e:00:54:12'),
            dev('eth2', 'pci-0000:00:03.0', '00:00:5e:00:54:13'),
            dev('eth3', 'pci-0000:00:04.0', '00:00:5e:00:54:14'),
            dev('eth4', 'pci-0000:00:02.0', '00:00:5e:00:54:19'),
        ]
        plan, _, report = resolve(devices, store)
        self.assertEqual(plan, {}, 'nothing may be renamed')
        names = final_names(report)
        self.assertEqual(names['00:00:5e:00:54:12'], 'eth1')
        self.assertEqual(names['00:00:5e:00:54:19'], 'eth4')

    def test_spare_nic_does_not_displace_configured_interfaces(self):
        """2026-09-02 #2: a fourth, unconfigured NIC was enough to make the
        three configured interfaces fail to get their hardware - eth1/eth2
        stayed bare while eth3/eth4/eth5 appeared holding the NICs.
        """
        devices = [
            dev('eth0', 'pci-0000:00:03.0', '00:00:5e:00:54:31'),
            dev('eth1', 'pci-0000:00:04.0', '00:00:5e:00:54:39'),
            dev('eth2', 'pci-0000:00:05.0', '00:00:5e:00:54:32'),
            dev('eth3', 'pci-0000:00:06.0', '00:00:5e:00:54:3c'),
        ]
        _, new_store, report = resolve(devices, empty_store())
        self.assertEqual(set(new_store['interfaces']),
                         {'eth0', 'eth1', 'eth2', 'eth3'})
        names = final_names(report)
        self.assertEqual(names['00:00:5e:00:54:31'], 'eth0')
        self.assertEqual(names['00:00:5e:00:54:39'], 'eth1')
        self.assertEqual(names['00:00:5e:00:54:32'], 'eth2')

    def test_config_node_without_hardware_does_not_block_the_others(self):
        """2026-09-09: eth0/eth1/eth2 configured with no hw-id on a two-NIC
        VM. Every interface was left pending, both NICs parked on eth3/eth4,
        and the box was unreachable from the network.
        """
        devices = [
            dev('eth0', 'pci-0000:00:03.0', '00:00:5e:00:54:a1'),
            dev('eth1', 'pci-0000:00:04.0', '00:00:5e:00:54:a9'),
        ]
        plan, new_store, report = resolve(devices, empty_store())
        # the two NICs present take eth0 and eth1; a configured eth2 node
        # simply has no hardware, which is a reporting matter not a naming one
        self.assertEqual(plan, {})
        names = final_names(report)
        self.assertEqual(names['00:00:5e:00:54:a1'], 'eth0')
        self.assertEqual(names['00:00:5e:00:54:a9'], 'eth1')
        self.assertNotIn('eth3', new_store['interfaces'])


class TestLinkFiles(unittest.TestCase):
    """The .link layer is what removes the rename window: udev applies the
    name as the device is added, so no probe-order name is ever observable.
    """

    def test_matches_the_same_property_the_store_keyed_on(self):
        # udev must apply exactly the mapping recorded in the store - if the
        # .link matched on anything else the two could disagree about what
        # identifies an interface
        body = render_link('eth1', 'ID_NET_NAME_SLOT=ens18')
        self.assertIn('Property=ID_NET_NAME_SLOT=ens18', body)
        self.assertIn('Name=eth1', body)
        self.assertIn('Type=ether', body)

    def test_the_address_policy_is_spelled_out(self):
        # only the first matching file is applied, so this one shadows the
        # policy the distribution ships. Without it a modem keeps the random
        # address its driver gives it, fresh on every boot.
        for name in ('eth1', 'wwan0'):
            body = render_link(name, 'ID_NET_NAME_PATH=wwp0s20f0u2u4c3')
            self.assertIn('MACAddressPolicy=persistent', body)

    def test_a_file_without_the_policy_is_rewritten(self):
        # the upgrade path: a box already carrying files from before only
        # picks this up if an existing one is replaced
        store = {'version': STORE_VERSION,
                 'interfaces': {'wwan0': 'ID_NET_NAME_PATH=wwp0s20f0u2u4c3'},
                 'hardware': {}}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / '10-vyos-wwan0.link'
            path.write_text('[Match]\nType=wwan\n\n[Link]\nName=wwan0\n')
            sync_link_files(store, Path(d))
            self.assertIn('MACAddressPolicy=persistent', path.read_text())

    def test_no_link_file_is_written_for_a_radio(self):
        # a .link keyed on a phy's address matches every interface created on
        # that phy, so writing one renamed the interface the operator had just
        # asked for. Wireless is named from the configuration instead.
        store = {'version': STORE_VERSION,
                 'interfaces': {'eth0': 'ID_PATH=pci-0000:00:12.0',
                                'wlan0': 'ID_NET_NAME_MAC=wlx020000000000'},
                 'hardware': {}}
        with tempfile.TemporaryDirectory() as d:
            written = sync_link_files(store, Path(d))
            names = [p.name for p in written]
        self.assertEqual(names, ['10-vyos-eth0.link'])

    def test_one_file_per_interface(self):
        with tempfile.TemporaryDirectory() as d:
            written = sync_link_files(
                store_of({'eth1': 'pci-0000:00:13.0'}), Path(d))
            self.assertEqual([p.name for p in written], ['10-vyos-eth1.link'])

    def test_stale_files_are_removed(self):
        with tempfile.TemporaryDirectory() as d:
            link_dir = Path(d)
            sync_link_files(store_of({'eth1': 'p1',
                                      'eth2': 'p2'}), link_dir)
            sync_link_files(store_of({'eth1': 'p1'}), link_dir)
            remaining = sorted(p.name for p in link_dir.glob('*.link'))
            self.assertEqual(remaining, ['10-vyos-eth1.link'])

    def test_operator_files_are_left_alone(self):
        with tempfile.TemporaryDirectory() as d:
            link_dir = Path(d)
            custom = link_dir / '99-my-tuning.link'
            custom.write_text('[Match]\nType=ether\n\n[Link]\nMTUBytes=9000\n')
            sync_link_files(store_of({'eth1': 'p1'}), link_dir)
            self.assertTrue(custom.exists())


class TestPortLabelGate(unittest.TestCase):
    """The adapter label only orders hardware the hypervisor presented.
    Physical servers label their ports too - "NIC1", "Embedded LOM 1 Port 1" -
    and reordering those would be the same bug on bare metal.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.dmi = os.path.join(self.tmp, 'sys_vendor')
        patch = mock.patch('vyos.ifconfig.ifname_store._DMI_SYS_VENDOR',
                           Path(self.dmi))
        patch.start()
        self.addCleanup(patch.stop)
        self._dmi('Dell Inc.')

    def _dmi(self, vendor):
        with open(self.dmi, 'w') as f:
            f.write(vendor + '\n')

    def _make(self, name, label=None, vendor=None, subsystem_vendor=None):
        device = os.path.join(self.tmp, name, 'device')
        os.makedirs(device)
        for attr, value in (('label', label), ('vendor', vendor),
                            ('subsystem_vendor', subsystem_vendor)):
            if value is not None:
                with open(os.path.join(device, attr), 'w') as f:
                    f.write(value + '\n')
        return name

    def test_label_index_is_parsed(self):
        self._make('eth0', label='Ethernet0')
        self._make('eth1', label='Ethernet10')
        self.assertEqual(port_label_index('eth0', self.tmp), 0)
        # not lexical - Ethernet10 must sort after Ethernet9
        self.assertEqual(port_label_index('eth1', self.tmp), 10)

    def test_labels_physical_servers_use_are_not_adapter_numbers(self):
        for i, label in enumerate(['NIC1', 'Integrated NIC 1', 'LAN1',
                                   'Embedded LOM 1 Port 1',
                                   'PCIe Slot 1 Port 1', 'Ethernet',
                                   'Ethernet0 Port 2', '']):
            name = self._make(f'eth{i}', label=label)
            self.assertEqual(port_label_index(name, self.tmp), _LABEL_UNKNOWN,
                              f'{label!r} was taken for an adapter number')

    def test_no_label_at_all(self):
        self._make('eth0')
        self.assertEqual(port_label_index('eth0', self.tmp), _LABEL_UNKNOWN)

    def test_a_vmware_nic_is_recognised_by_its_pci_vendor_alone(self):
        # DMI says Dell - smbios.reflectHost does exactly this, and a gate on
        # DMI alone would switch itself off
        self._make('eth0', vendor='0x15ad')                  # vmxnet3
        self._make('eth1', subsystem_vendor='0x15ad')        # emulated e1000
        self.assertTrue(is_vmware_nic('eth0', self.tmp))
        self.assertTrue(is_vmware_nic('eth1', self.tmp))

    def test_dmi_still_catches_a_model_whose_pci_ids_are_unknown(self):
        self._make('eth0', vendor='0x1af4')
        self._dmi('VMware, Inc.')
        self.assertTrue(is_vmware_nic('eth0', self.tmp))

    def test_a_physical_nic_is_left_alone(self):
        self._make('eth0', label='Ethernet0',
                   vendor='0x8086', subsystem_vendor='0x8086')
        self.assertFalse(is_vmware_nic('eth0', self.tmp))


class TestPermanentMac(unittest.TestCase):
    """Reading the hardware's own address matters wherever a custom MAC may
    be in effect: the current address is then the custom one. This used to
    come from the hw-id node, which could also simply be stale.
    """

    def test_ethtool_permanent_address(self):
        with mock.patch('vyos.ifconfig.ifname_store.rc_cmd',
                        return_value=(0, 'Permanent address: aa:bb:cc:dd:ee:ff\n')):
            self.assertEqual(permanent_mac('eth0'), 'aa:bb:cc:dd:ee:ff')

    def test_zero_address_falls_back_to_sysfs(self):
        # some drivers report an all-zero "unsupported" permanent address
        # instead of failing outright
        with mock.patch('vyos.ifconfig.ifname_store.rc_cmd',
                        return_value=(0, 'Permanent address: 00:00:00:00:00:00\n')), \
             mock.patch('pathlib.Path.read_text', return_value='11:22:33:44:55:66\n'):
            self.assertEqual(permanent_mac('eth0'), '11:22:33:44:55:66')

    def test_ethtool_unsupported_falls_back_to_sysfs(self):
        with mock.patch('vyos.ifconfig.ifname_store.rc_cmd',
                        return_value=(1, 'Operation not supported')), \
             mock.patch('pathlib.Path.read_text', return_value='11:22:33:44:55:66\n'):
            self.assertEqual(permanent_mac('eth0'), '11:22:33:44:55:66')

    def test_no_mac_available_returns_empty(self):
        with mock.patch('vyos.ifconfig.ifname_store.rc_cmd', return_value=(1, '')), \
             mock.patch('pathlib.Path.read_text', side_effect=OSError):
            self.assertEqual(permanent_mac('eth0'), '')


class TestDiscoverDevices(unittest.TestCase):
    """Only real, independently-addressable hardware is a naming candidate.
    Virtual interfaces have no bus device; SR-IOV VFs and hypervisor VF
    datapaths are acceleration children sharing another interface's MAC, so
    naming them would invent a second interface for one physical port. Being
    a member of a bridge, bond or VRF says nothing about the hardware.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        for patch in (mock.patch('vyos.ifconfig.ifname_store.read_properties',
                                 return_value={}),
                      mock.patch('vyos.ifconfig.ifname_store.rc_cmd',
                                 return_value=(1, ''))):
            patch.start()
            self.addCleanup(patch.stop)

        def make(name, mac=None, has_device=True, enslaved=False, is_vf=False,
                 master_is_device=False, wwan=False):
            path = os.path.join(self.tmp, name)
            os.mkdir(path)
            if has_device:
                os.mkdir(os.path.join(path, 'device'))
            if is_vf:
                pf = os.path.join(self.tmp, f'{name}_pf')
                os.mkdir(pf)
                os.symlink(pf, os.path.join(path, 'device', 'physfn'))
            if enslaved:
                master = os.path.join(self.tmp, f'{name}_master')
                os.mkdir(master)
                if master_is_device:
                    os.mkdir(os.path.join(master, 'device'))
                os.symlink(master, os.path.join(path, 'master'))
            if mac:
                with open(os.path.join(path, 'address'), 'w') as f:
                    f.write(mac + '\n')
            if wwan:
                with open(os.path.join(path, 'uevent'), 'w') as f:
                    f.write('DEVTYPE=wwan\n')

        self.make = make
        make('eth0', mac='aa:aa:aa:aa:aa:00')
        make('eth1', mac='aa:aa:aa:aa:aa:01')
        make('br0', mac='aa:aa:aa:aa:aa:99', has_device=False)
        make('lo', has_device=False)
        make('eth8', mac='aa:aa:aa:aa:aa:08', enslaved=True)
        make('eth7', mac='aa:aa:aa:aa:aa:07', enslaved=True,
             master_is_device=True)
        make('eth9', mac='aa:aa:aa:aa:aa:09', is_vf=True)
        make('vf_eth0', mac='aa:aa:aa:aa:aa:00')

    def _names(self):
        return {d['name'] for d in discover_devices(self.tmp)}

    def test_only_physical_independent_interfaces(self):
        self.assertEqual(self._names(), {'eth0', 'eth1', 'eth8'})

    def test_a_modem_is_discovered_without_an_address(self):
        # a modem is given a random address at each probe, so recording it
        # would make the same modem look like different hardware every boot
        self.make('wwan0', mac='b6:53:dd:66:c2:98', wwan=True)
        devices = {d['name']: d for d in discover_devices(self.tmp)}
        self.assertIn('wwan0', devices)
        self.assertEqual(devices['wwan0']['mac'], '')
        self.assertTrue(devices['wwan0']['wwan'])

    def test_a_card_with_no_address_is_still_skipped(self):
        # only a modem is kept without one
        self.make('eth5')
        self.assertNotIn('eth5', self._names())

    def test_virtual_interfaces_excluded(self):
        self.assertNotIn('br0', self._names())
        self.assertNotIn('lo', self._names())

    def test_bridge_or_bond_member_still_discovered(self):
        # a member is still its own card, in its own slot. Dropping it here
        # would report the hardware as missing for as long as it is in use.
        self.assertIn('eth8', self._names())

    def test_vf_datapath_enslaved_to_its_parent_excluded(self):
        # the accelerated path is enslaved to the interface it belongs to,
        # which - unlike a bridge or a bond - is a device itself
        self.assertNotIn('eth7', self._names())

    def test_sriov_virtual_function_excluded(self):
        # the general marker, independent of hypervisor - the previous
        # exclusion relied on udev rules scoped to a Microsoft DMI vendor
        # string and would miss a bare-metal Mellanox VF
        self.assertNotIn('eth9', self._names())

    def test_hypervisor_vf_datapath_excluded(self):
        # parked as vf_* by 63-hyperv-vf-net.rules; shares its synthetic
        # parent's MAC and must not be taken for a second interface
        self.assertNotIn('vf_eth0', self._names())
