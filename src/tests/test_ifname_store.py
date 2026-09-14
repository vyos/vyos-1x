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

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vyos.ifconfig.ifname_store import STORE_VERSION
from vyos.ifconfig.ifname_store import canonical_sort_key
from vyos.ifconfig.ifname_store import device_matches
from vyos.ifconfig.ifname_store import ambiguous_keys
from vyos.ifconfig.ifname_store import hardware_key
from vyos.ifconfig.ifname_store import discover_devices
from vyos.ifconfig.ifname_store import empty_store
from vyos.ifconfig.ifname_store import load_store
from vyos.ifconfig.ifname_store import permanent_mac
from vyos.ifconfig.ifname_store import render_link
from vyos.ifconfig.ifname_store import resolve
from vyos.ifconfig.ifname_store import sync_link_files
from vyos.ifconfig.ifname_store import save_store


def dev(name, path, mac, wireless=False, bus='pci'):
    """A device sitting at 'path'. Its key is what udev would report for it -
    here the raw ID_PATH, which is what a plain virtio or e1000e NIC with no
    firmware slot index ends up keyed on."""
    properties = {'ID_PATH': path, 'ID_BUS': bus} if path else {}
    return {'name': name, 'mac': mac, 'wireless': wireless,
            'properties': properties,
            'key': hardware_key(properties)}


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


class TestStoreIO(unittest.TestCase):
    @staticmethod
    def _config_dir(d):
        """A directory that looks like a properly mounted config volume."""
        (Path(d) / '.vyatta_config').touch()
        return Path(d) / 'interface-mapping.json'

    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._config_dir(d)
            s = store_of({'eth0': 'pci-0000:00:12.0'})
            self.assertTrue(save_store(s, p))
            self.assertEqual(load_store(p), s)

    def test_refuses_to_write_when_config_volume_is_not_mounted(self):
        # TPM/LUKS unlock failed: vyos-router continues, but persisting here
        # would write a shadow store that the real volume masks later
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'interface-mapping.json'   # no .vyatta_config marker
            self.assertFalse(save_store(store_of({'eth0': 'x'}), p))
            self.assertFalse(p.exists())

    def test_missing_file_is_empty_store(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(load_store(Path(d) / 'nope.json'), empty_store())

    def test_corrupt_file_is_empty_store(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._config_dir(d)
            p.write_text('{ this is not json')
            self.assertEqual(load_store(p), empty_store())

    def test_write_is_atomic_no_leftovers(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._config_dir(d)
            save_store(store_of({'eth0': 'pci-0000:00:12.0'}), p)
            self.assertEqual(sorted(f.name for f in Path(d).iterdir()),
                             ['.vyatta_config', 'interface-mapping.json'])


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

    def test_wireless_uses_its_own_namespace(self):
        devices = [dev('eth0', 'pci-0000:00:12.0', 'aa:aa:aa:aa:aa:aa'),
                   dev('wlan5', 'pci-0000:00:14.0', 'cc:cc:cc:cc:cc:cc',
                       wireless=True)]
        _, new_store, _ = resolve(devices, empty_store())
        self.assertIn('eth0', new_store['interfaces'])
        self.assertIn('wlan0', new_store['interfaces'])


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

    def test_link_for_a_radio_matches_the_wireless_type(self):
        # a .link naming a type the device is not never applies, so a radio
        # rendered as 'ether' would silently keep its probe-order name
        body = render_link('wlan0', 'ID_PATH=pci-0000:00:14.0')
        self.assertIn('Type=wlan', body)
        self.assertNotIn('Type=ether', body)
        self.assertIn('Name=wlan0', body)

    def test_radio_named_by_resolve_gets_a_wireless_link(self):
        # end to end: resolve() names by type, and the file written for that
        # name has to agree with it
        devices = [dev('wlan5', 'pci-0000:00:14.0', 'aa:aa:aa:aa:aa:01',
                        wireless=True),
                   dev('eth9', 'pci-0000:00:12.0', 'bb:bb:bb:bb:bb:02')]
        _, store, _ = resolve(devices, empty_store())
        self.assertIn('wlan0', store['interfaces'])
        with tempfile.TemporaryDirectory() as d:
            written = sync_link_files(store, Path(d))
            bodies = {p.name: p.read_text() for p in written}
        self.assertIn('Type=wlan', bodies['10-vyos-wlan0.link'])
        self.assertIn('Type=ether', bodies['10-vyos-eth0.link'])

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
    Virtual interfaces have no bus device; enslaved interfaces, SR-IOV VFs
    and hypervisor VF datapaths are acceleration children that share another
    interface's MAC, so naming them would invent a second interface for one
    physical port.
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

        def make(name, mac=None, has_device=True, enslaved=False, is_vf=False):
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
                os.symlink(master, os.path.join(path, 'master'))
            if mac:
                with open(os.path.join(path, 'address'), 'w') as f:
                    f.write(mac + '\n')

        make('eth0', mac='aa:aa:aa:aa:aa:00')
        make('eth1', mac='aa:aa:aa:aa:aa:01')
        make('br0', mac='aa:aa:aa:aa:aa:99', has_device=False)
        make('lo', has_device=False)
        make('eth8', mac='aa:aa:aa:aa:aa:08', enslaved=True)
        make('eth9', mac='aa:aa:aa:aa:aa:09', is_vf=True)
        make('vf_eth0', mac='aa:aa:aa:aa:aa:00')

    def _names(self):
        return {d['name'] for d in discover_devices(self.tmp)}

    def test_only_physical_independent_interfaces(self):
        self.assertEqual(self._names(), {'eth0', 'eth1'})

    def test_virtual_interfaces_excluded(self):
        self.assertNotIn('br0', self._names())
        self.assertNotIn('lo', self._names())

    def test_enslaved_interface_excluded(self):
        self.assertNotIn('eth8', self._names())

    def test_sriov_virtual_function_excluded(self):
        # the general marker, independent of hypervisor - the previous
        # exclusion relied on udev rules scoped to a Microsoft DMI vendor
        # string and would miss a bare-metal Mellanox VF
        self.assertNotIn('eth9', self._names())

    def test_hypervisor_vf_datapath_excluded(self):
        # parked as vf_* by 63-hyperv-vf-net.rules; shares its synthetic
        # parent's MAC and must not be taken for a second interface
        self.assertNotIn('vf_eth0', self._names())
