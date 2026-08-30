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
# Coverage for T3871 (boot race on hw-id based interface naming): the
# MAC-driven, collision-safe rename plan that replaces the old per-uevent
# udev decision, the find_available() crash it used to hit, the
# ethtool/sysfs permanent-MAC fallback, and the config.boot-availability
# ordering corner case (vyos-net-name-resolve must run from inside
# vyos-router, after the config directory is mounted/decrypted, not as an
# independently-scheduled early-boot unit).

import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from helper import prepare_module

_here = os.path.dirname(__file__)

resolver = prepare_module(
    os.path.join(_here, '../system/vyos-net-name-resolve.py'),
    'vyos_net_name_resolve')
vyos_net_name = prepare_module(
    os.path.join(_here, '../udev/vyos_net_name'),
    'vyos_net_name')


class TestGetPendingHwidNodes(unittest.TestCase):
    """A node that exists under interfaces/{ethernet,wireless} but has no
    hw-id (e.g. after `delete interfaces ethernet eth1 hw-id`, the
    documented "NIC replaced" remediation) must be surfaced separately
    from the MAC-keyed configured dict, since it has no MAC to key by yet
    - this is what lets main() try to reclaim it for the exact NIC that
    vacated it, instead of silently orphaning its other settings.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.config_path = os.path.join(self.tmp, 'config.boot')
        self._orig_config_path = resolver.config_path
        resolver.config_path = self.config_path
        self.addCleanup(setattr, resolver, 'config_path', self._orig_config_path)

    def _write_config(self, text):
        with open(self.config_path, 'w') as f:
            f.write(text)

    def test_node_with_hwid_not_pending(self):
        self._write_config(
            'interfaces {\n'
            '    ethernet eth0 {\n'
            '        hw-id 00:11:22:33:44:55\n'
            '    }\n'
            '}\n'
        )
        self.assertEqual(resolver.get_pending_hwid_nodes(),
                          {'ethernet': set(), 'wireless': set()})

    def test_node_without_hwid_is_pending(self):
        self._write_config(
            'interfaces {\n'
            '    ethernet eth1 {\n'
            '        address 10.99.1.1/24\n'
            '    }\n'
            '}\n'
        )
        self.assertEqual(resolver.get_pending_hwid_nodes(),
                          {'ethernet': {'eth1'}, 'wireless': set()})

    def test_mixed_ethernet_and_wireless(self):
        self._write_config(
            'interfaces {\n'
            '    ethernet eth0 {\n'
            '        hw-id 00:11:22:33:44:55\n'
            '    }\n'
            '    ethernet eth1 {\n'
            '        address 10.99.1.1/24\n'
            '    }\n'
            '    wireless wlan0 {\n'
            '        ssid example\n'
            '    }\n'
            '}\n'
        )
        self.assertEqual(resolver.get_pending_hwid_nodes(),
                          {'ethernet': {'eth1'}, 'wireless': {'wlan0'}})

    def test_no_interfaces_section(self):
        self._write_config('system {\n    host-name vyos\n}\n')
        self.assertEqual(resolver.get_pending_hwid_nodes(),
                          {'ethernet': set(), 'wireless': set()})

    def test_no_config_boot_at_all(self):
        # livecd/ISO case - config_path doesn't exist
        self.assertEqual(resolver.get_pending_hwid_nodes(),
                          {'ethernet': set(), 'wireless': set()})


class TestFindAvailableCrashFix(unittest.TestCase):
    """find_available() used to raise IndexError on an empty candidate set
    (index_list[0]) and ValueError on a name with no trailing digit
    (int('')) - both are realistic inputs on a box's first boot, or when a
    biosdevname/predefined name has no numeric suffix.
    """

    def test_resolver_empty_set(self):
        self.assertEqual(resolver.find_available(set(), 'eth'), 'eth0')

    def test_resolver_no_prefix_match(self):
        self.assertEqual(resolver.find_available({'wlan3'}, 'eth'), 'eth0')

    def test_resolver_contiguous(self):
        names = {'eth0', 'eth1', 'eth2'}
        self.assertEqual(resolver.find_available(names, 'eth'), 'eth3')

    def test_resolver_fills_hole(self):
        self.assertEqual(resolver.find_available({'eth2', 'eth5'}, 'eth'), 'eth3')

    def test_resolver_no_hole_appends(self):
        self.assertEqual(resolver.find_available({'eth2', 'eth3'}, 'eth'), 'eth4')

    def test_vyos_net_name_empty_dict(self):
        self.assertEqual(vyos_net_name.find_available({}, 'eth'), 'eth0')

    def test_vyos_net_name_no_digit_suffix(self):
        self.assertEqual(
            vyos_net_name.find_available({'m': 'wlan3'}, 'eth'), 'eth0')

    def test_vyos_net_name_contiguous(self):
        intfs = {'a': 'eth0', 'b': 'eth1'}
        self.assertEqual(vyos_net_name.find_available(intfs, 'eth'), 'eth2')

    def test_vyos_net_name_is_available(self):
        self.assertTrue(vyos_net_name.is_available({'a': 'eth0'}, 'eth1'))
        self.assertFalse(vyos_net_name.is_available({'a': 'eth0'}, 'eth0'))

    def test_vyos_net_name_mod_ifname(self):
        self.assertEqual(vyos_net_name.mod_ifname('e5'), 'eth3')
        self.assertEqual(vyos_net_name.mod_ifname('e2'), 'eth0')
        self.assertEqual(vyos_net_name.mod_ifname('e1'), 'eth1')
        self.assertEqual(vyos_net_name.mod_ifname('wlan0'), 'wlan0')


class TestUnmatchedCandidates(unittest.TestCase):
    """Field report: an unconfigured NIC that happens to be squatting on a
    DIFFERENT interface's configured hw-id slot this boot (e.g. due to
    probe-order scrambling) was excluded here just because
    compute_rename_plan() already scheduled it for eviction. That skipped
    it past match_pending_nodes() entirely, so a squatter that was really
    the exact NIC a pending node should reclaim - or one that made a
    reclaim genuinely ambiguous - fell through to ordinary bootstrap
    naming and got a permanent hw-id with no ambiguity check at all.
    Squatters must stay in this pool; only their eviction destination
    (still computed by compute_rename_plan()) is a fallback, not a reason
    to hide them from reclaim/ambiguity handling.
    """

    def test_squatter_is_still_a_candidate(self):
        configured = {'m0': 'eth1'}
        current = {'eth1': 'squatter-mac', 'eth9': 'm0'}
        existing_plan = {'eth1': 'eth3', 'eth9': 'eth1'}
        candidates = resolver.unmatched_candidates(configured, current, existing_plan)
        self.assertEqual(candidates, [('squatter-mac', 'eth1')])

    def test_rightful_owner_still_excluded(self):
        configured = {'m0': 'eth0'}
        current = {'eth0': 'm0'}
        candidates = resolver.unmatched_candidates(configured, current, {})
        self.assertEqual(candidates, [])


class TestMatchPendingNodes(unittest.TestCase):
    """A pending node's hw-id is unknown by construction - there's no MAC
    to check a candidate against - so matching only ever happens on an
    exact cover: as many pending nodes of a type as unconfigured
    candidates of that type. Confirmed in the field: a naive
    deterministic fill (sorting pending nodes and candidates together
    like numeric gaps) silently bound a configured node's address to a
    different physical NIC than its own, because an already-provisioned
    box's existing names have no relationship to PCIe/MAC sort order.
    With MORE candidates than nodes there is no way to tell which one is
    the node's own hardware, so nothing is matched.

    An exact cover is a different situation: every node receives real
    hardware whatever happens, so only the permutation is open, and
    refusing strands 100% of the nodes on interfaces that do not exist
    (the multi-NIC cloud-init report). Those are paired in canonical
    hardware order, which is why pcie_address is pinned below.
    """

    def setUp(self):
        patcher = mock.patch.object(resolver, 'is_wireless_interface',
                                     return_value=False)
        self.is_wireless = patcher.start()
        self.addCleanup(patcher.stop)

        # see TestComputeBootstrapPlan.setUp() - keep the canonical order
        # off the build host's real sysfs, so these exercise MAC rank
        distance_patcher = mock.patch.object(resolver, 'pcie_distance',
                                              return_value=0)
        self.pcie_distance = distance_patcher.start()
        self.addCleanup(distance_patcher.stop)

        address_patcher = mock.patch.object(
            resolver, 'pcie_address',
            return_value=resolver.PCIE_ADDRESS_UNKNOWN)
        self.pcie_address = address_patcher.start()
        self.addCleanup(address_patcher.stop)

    def test_unambiguous_single_pending_single_candidate_matches(self):
        pending = {'ethernet': {'eth1'}, 'wireless': set()}
        candidates = [('m1', 'eth9')]
        matched = resolver.match_pending_nodes(pending, candidates)
        self.assertEqual(matched, {'m1': 'eth1'})

    def test_two_pending_one_candidate_no_match(self):
        # can't tell which of the two pending nodes this one candidate
        # belongs to - neither is matched.
        pending = {'ethernet': {'eth1', 'eth4'}, 'wireless': set()}
        candidates = [('m1', 'eth9')]
        matched = resolver.match_pending_nodes(pending, candidates)
        self.assertEqual(matched, {})

    def test_exact_cover_pairs_in_canonical_hardware_order(self):
        # the multi-NIC cloud-init shape: two address-bearing nodes with
        # no hw-id and exactly two unconfigured NICs. Refusing here would
        # strand BOTH addresses on interfaces that never come to exist,
        # so they are paired - lowest node index to first-sorted hardware.
        pending = {'ethernet': {'eth1', 'eth2'}, 'wireless': set()}
        candidates = [('bb', 'eth8'), ('aa', 'eth9')]
        matched = resolver.match_pending_nodes(pending, candidates)
        self.assertEqual(matched, {'aa': 'eth1', 'bb': 'eth2'})

    def test_exact_cover_pairs_by_pci_slot_not_mac_magnitude(self):
        # the reported silent-swap shape: hardware order must come from
        # the PCI address, not from raw MAC rank - here the numerically
        # LOWER mac sits in the HIGHER slot and must get the higher name.
        self.pcie_address.side_effect = lambda name: {
            'eth8': ((0, 0, 5, 0),),
            'eth9': ((0, 0, 6, 0),),
        }[name]
        pending = {'ethernet': {'eth1', 'eth2'}, 'wireless': set()}
        candidates = [('52:54:00:00:00:22', 'eth9'),
                      ('52:54:00:ff:00:21', 'eth8')]
        matched = resolver.match_pending_nodes(pending, candidates)
        self.assertEqual(matched, {'52:54:00:ff:00:21': 'eth1',
                                    '52:54:00:00:00:22': 'eth2'})

    def test_exact_cover_orders_node_names_numerically(self):
        # 'eth10' must pair after 'eth2', not before it as a plain
        # lexical sort of the names would have it.
        pending = {'ethernet': {'eth2', 'eth10'}, 'wireless': set()}
        candidates = [('aa', 'eth8'), ('bb', 'eth9')]
        matched = resolver.match_pending_nodes(pending, candidates)
        self.assertEqual(matched, {'aa': 'eth2', 'bb': 'eth10'})

    def test_three_pending_three_candidates_cover(self):
        pending = {'ethernet': {'eth0', 'eth1', 'eth2'}, 'wireless': set()}
        candidates = [('cc', 'eth7'), ('aa', 'eth9'), ('bb', 'eth8')]
        matched = resolver.match_pending_nodes(pending, candidates)
        self.assertEqual(matched, {'aa': 'eth0', 'bb': 'eth1', 'cc': 'eth2'})

    def test_three_pending_two_candidates_no_match(self):
        pending = {'ethernet': {'eth0', 'eth1', 'eth2'}, 'wireless': set()}
        candidates = [('aa', 'eth9'), ('bb', 'eth8')]
        matched = resolver.match_pending_nodes(pending, candidates)
        self.assertEqual(matched, {})

    def test_two_pending_three_candidates_no_match(self):
        # one candidate too many - the field-reported "unrelated interface
        # freed in the same boot" hazard, at a larger cardinality.
        pending = {'ethernet': {'eth0', 'eth1'}, 'wireless': set()}
        candidates = [('aa', 'eth9'), ('bb', 'eth8'), ('cc', 'eth7')]
        matched = resolver.match_pending_nodes(pending, candidates)
        self.assertEqual(matched, {})

    def test_covers_are_judged_per_type_not_across_types(self):
        # ethernet covers 2:2 while wireless is 1:2 - the ethernet nodes
        # are still paired, and the wireless one is still left pending.
        self.is_wireless.side_effect = lambda name: name.startswith('radio')
        pending = {'ethernet': {'eth1', 'eth2'}, 'wireless': {'wlan0'}}
        candidates = [('aa', 'eth9'), ('bb', 'eth8'),
                      ('cc', 'radio0'), ('dd', 'radio1')]
        matched = resolver.match_pending_nodes(pending, candidates)
        self.assertEqual(matched, {'aa': 'eth1', 'bb': 'eth2'})

    def test_one_pending_two_candidates_no_match(self):
        # the field-reported shape: an unrelated second candidate (e.g.
        # freed by a different interface's config being fully deleted in
        # the same boot) is enough to make this genuinely ambiguous, even
        # though it isn't itself pending anything.
        pending = {'ethernet': {'eth1'}, 'wireless': set()}
        candidates = [('m1', 'eth9'), ('m2', 'eth8')]
        matched = resolver.match_pending_nodes(pending, candidates)
        self.assertEqual(matched, {})

    def test_ethernet_and_wireless_matched_independently(self):
        self.is_wireless.side_effect = lambda name: name == 'radio0'
        pending = {'ethernet': {'eth1'}, 'wireless': {'wlan2'}}
        candidates = [('m1', 'ifaceB'), ('m2', 'radio0')]
        matched = resolver.match_pending_nodes(pending, candidates)
        self.assertEqual(matched, {'m1': 'eth1', 'm2': 'wlan2'})

    def test_no_pending_returns_empty(self):
        pending = {'ethernet': set(), 'wireless': set()}
        candidates = [('m1', 'eth9')]
        matched = resolver.match_pending_nodes(pending, candidates)
        self.assertEqual(matched, {})


class TestComputeRenamePlan(unittest.TestCase):
    """The authoritative rename plan is what fixes the multi-vendor NIC
    boot race: it is driven purely by MAC address, independent of
    ifindex/probe order, and must never produce a colliding assignment.
    """

    def test_noop_when_already_correct(self):
        configured = {'m0': 'eth0', 'm1': 'eth1'}
        current = {'eth0': 'm0', 'eth1': 'm1'}
        self.assertEqual(resolver.compute_rename_plan(configured, current), {})

    def test_rename_independent_of_probe_order(self):
        # m0/m1 landed on unrelated names this boot (e.g. a different
        # vendor driver won the probe race) - the plan must still point
        # them at their configured targets regardless.
        configured = {'m0': 'eth0', 'm1': 'eth1'}
        current = {'eth5': 'm0', 'eth3': 'm1'}
        plan = resolver.compute_rename_plan(configured, current)
        self.assertEqual(plan, {'eth5': 'eth0', 'eth3': 'eth1'})

    def test_full_swap_cycle(self):
        # eth0 and eth1 need to trade names - a naive from->to rename
        # would collide; the two-phase scratch-name staging must not.
        configured = {'m0': 'eth1', 'm1': 'eth0'}
        current = {'eth0': 'm0', 'eth1': 'm1'}
        plan = resolver.compute_rename_plan(configured, current)
        self.assertEqual(plan, {'eth0': 'eth1', 'eth1': 'eth0'})

    def test_squatter_relocated(self):
        # an unconfigured interface currently sits on a name a configured
        # hw-id needs - it must be moved out of the way, not left there.
        configured = {'m0': 'eth0'}
        current = {'eth0': 'unconfigured-mac', 'eth5': 'm0'}
        plan = resolver.compute_rename_plan(configured, current)
        self.assertEqual(plan['eth5'], 'eth0')
        self.assertNotEqual(plan['eth0'], 'eth0')
        self.assertTrue(plan['eth0'].startswith('eth'))

    def test_squatter_never_relocated_onto_a_missing_hwid_target(self):
        # macMissing's hardware hasn't shown up this boot (removed/faulty/
        # slow driver), so its reserved target 'eth1' never appears in
        # `current` and the main hw-id loop skips it entirely (source is
        # None) - the squatter being relocated off of 'eth0' must still not
        # be handed 'eth1', or it would need relocating again the moment
        # that hardware actually appears.
        configured = {'macA': 'eth0', 'macMissing': 'eth1'}
        current = {'eth0': 'squatterMac', 'eth2': 'macA'}
        plan = resolver.compute_rename_plan(configured, current)
        self.assertEqual(plan.get('eth2'), 'eth0')
        self.assertNotEqual(plan.get('eth0'), 'eth1')

    def test_squatter_never_relocated_onto_a_pending_hwid_less_node(self):
        # 'eth1' has no hw-id at all (e.g. `delete interfaces ethernet
        # eth1 hw-id`, the documented remediation for a replaced NIC) but
        # its config node - and settings like address - still exist. A
        # squatter being relocated off of 'eth0' must not be handed 'eth1'
        # either, or it would permanently steal the exact slot the
        # original NIC needs to reclaim.
        configured = {'macA': 'eth0'}
        pending = {'ethernet': {'eth1'}, 'wireless': set()}
        current = {'eth0': 'squatterMac', 'eth2': 'macA'}
        plan = resolver.compute_rename_plan(configured, current, pending)
        self.assertEqual(plan.get('eth2'), 'eth0')
        self.assertNotEqual(plan.get('eth0'), 'eth1')

    def test_missing_hardware_no_crash_no_entry(self):
        # hw-id configured but the NIC never showed up (missing/faulty) -
        # must be skipped, not crash or incorrectly assign another interface.
        configured = {'m0': 'eth0', 'missing-mac': 'eth9'}
        current = {'eth5': 'm0'}
        plan = resolver.compute_rename_plan(configured, current)
        self.assertEqual(plan, {'eth5': 'eth0'})

    def test_rename_introducing_a_gap(self):
        # user edits the CLI so m2's node is renamed eth2 -> eth10 while
        # keeping the same hw-id, leaving eth5..eth9 unused.
        configured = {
            'm0': 'eth0', 'm1': 'eth1', 'm2': 'eth10',
            'm3': 'eth3', 'm4': 'eth4',
        }
        current = {
            'eth0': 'm0', 'eth1': 'm1', 'eth2': 'm2',
            'eth3': 'm3', 'eth4': 'm4',
        }
        plan = resolver.compute_rename_plan(configured, current)
        self.assertEqual(plan, {'eth2': 'eth10'})

    def test_rename_introducing_a_gap_with_scrambled_fastpath(self):
        # same as above, but this boot's cosmetic udev fast-path lands m2
        # on an unrelated name and coincidentally puts a different NIC on
        # the now-meaningless old 'eth2'.
        configured = {
            'm0': 'eth0', 'm1': 'eth1', 'm2': 'eth10',
            'm3': 'eth3', 'm4': 'eth4',
        }
        current = {
            'eth0': 'm0', 'eth1': 'm1', 'eth7': 'm2',
            'eth2': 'm3', 'eth4': 'm4',
        }
        plan = resolver.compute_rename_plan(configured, current)
        self.assertEqual(plan.get('eth7'), 'eth10')
        self.assertEqual(plan.get('eth2'), 'eth3')
        self.assertNotIn('eth2', configured.values())


class TestWaitForSettle(unittest.TestCase):
    """There is no specific MAC to wait for when bootstrap-naming hardware
    without a configured hw-id, so settling is detected as N consecutive
    identical discover_physical_interfaces() snapshots instead.
    """

    def test_returns_after_n_consecutive_stable_polls(self):
        snapshots = [
            {'eth0': 'm0'},           # still changing
            {'eth0': 'm0', 'eth1': 'm1'},  # still changing
            {'eth0': 'm0', 'eth1': 'm1'},  # 1st stable repeat
            {'eth0': 'm0', 'eth1': 'm1'},  # 2nd stable repeat -> settled
        ]
        with mock.patch.object(resolver, 'discover_physical_interfaces',
                                side_effect=snapshots):
            result = resolver.wait_for_settle(
                {}, timeout=5, poll=0, stable_polls=3)
        self.assertEqual(result, {'eth0': 'm0', 'eth1': 'm1'})

    def test_bounded_by_timeout_when_never_stable(self):
        counter = iter(range(1000))

        def ever_changing(*_a, **_kw):
            return {'eth0': f'm{next(counter)}'}

        clock = iter([0, 0.1, 20, 20])
        with mock.patch.object(resolver, 'discover_physical_interfaces',
                                side_effect=ever_changing), \
             mock.patch('time.monotonic', side_effect=lambda: next(clock)):
            result = resolver.wait_for_settle(
                {}, timeout=10, poll=0, stable_polls=3)
        # must return SOMETHING (the last snapshot seen), not hang or crash
        self.assertIn('eth0', result)

    def test_stable_polls_of_one_returns_on_initial_snapshot(self):
        with mock.patch.object(resolver, 'discover_physical_interfaces') as m:
            result = resolver.wait_for_settle(
                {'eth0': 'm0'}, timeout=5, poll=0, stable_polls=1)
        m.assert_not_called()
        self.assertEqual(result, {'eth0': 'm0'})


class TestIsWirelessInterface(unittest.TestCase):
    """Wireless detection must be race-free - it has to be correct even
    when the interface's current name is a leftover from the cosmetic
    udev-time fast path and doesn't look like a wlan name at all.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # phy80211 is always a symlink to a real sysfs node in practice -
        # exists() follows symlinks, so the test target must actually exist
        self.phy_target = os.path.join(self.tmp, 'phy0')
        os.mkdir(self.phy_target)

    def test_phy80211_present_is_wireless(self):
        path = os.path.join(self.tmp, 'wlan0')
        os.mkdir(path)
        os.symlink(self.phy_target, os.path.join(path, 'phy80211'))
        self.assertTrue(resolver.is_wireless_interface('wlan0', self.tmp))

    def test_no_phy80211_is_not_wireless(self):
        os.mkdir(os.path.join(self.tmp, 'eth0'))
        self.assertFalse(resolver.is_wireless_interface('eth0', self.tmp))

    def test_detection_independent_of_misleading_name(self):
        # named like a leftover cosmetic ethernet guess, but it's a real
        # wifi card - must still be classified wireless
        path = os.path.join(self.tmp, 'eth7')
        os.mkdir(path)
        os.symlink(self.phy_target, os.path.join(path, 'phy80211'))
        self.assertTrue(resolver.is_wireless_interface('eth7', self.tmp))


class TestPcieDistance(unittest.TestCase):
    """PCIe hop-depth is what lets bootstrap naming reflect physical slot
    position instead of raw MAC magnitude - a NIC wired straight to the
    root complex must not sort after an add-in card just because its MAC
    happens to be numerically higher.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # fake /sys/devices tree, separate from the fake /sys/class/net
        # entries, so symlink targets can point at realistic PCI-bus-shaped
        # paths the way a real /sys/class/net/<if>/device symlink does
        self.devices_root = os.path.join(self.tmp, 'devices')
        os.makedirs(self.devices_root)

    def _make_iface_pointing_at(self, name, *path_segments):
        """Create <tmp>/<name>/device as a symlink to a fake sysfs device
        node at devices_root/<path_segments...>.
        """
        target = os.path.join(self.devices_root, *path_segments)
        os.makedirs(target, exist_ok=True)
        iface_path = os.path.join(self.tmp, name)
        os.mkdir(iface_path)
        os.symlink(target, os.path.join(iface_path, 'device'))

    def test_shallow_device_one_pci_segment(self):
        # e.g. a NIC directly under the root complex: pci0000:00/0000:00:1f.6
        self._make_iface_pointing_at('eth0', 'pci0000:00', '0000:00:1f.6')
        self.assertEqual(resolver.pcie_distance('eth0', self.tmp), 1)

    def test_deep_device_behind_bridges(self):
        # e.g. an add-in card behind two cascaded PCIe bridges
        self._make_iface_pointing_at(
            'eth1', 'pci0000:00', '0000:00:1c.0',
            '0000:01:00.0', '0000:02:04.0')
        self.assertEqual(resolver.pcie_distance('eth1', self.tmp), 3)

    def test_virtio_indirection_not_miscounted(self):
        # verified-real virtio_net layout: device -> virtioN node, whose
        # OWN parent is the true PCI BDF - the virtioN segment itself must
        # be skipped, not counted as a hop.
        self._make_iface_pointing_at(
            'eth2', 'pci0000:00', '0000:00:12.0', 'virtio2', 'net')
        self.assertEqual(resolver.pcie_distance('eth2', self.tmp), 1)

    def test_missing_device_symlink_returns_sentinel(self):
        os.mkdir(os.path.join(self.tmp, 'eth3'))  # no 'device' entry at all
        self.assertEqual(resolver.pcie_distance('eth3', self.tmp),
                          resolver.PCIE_DISTANCE_UNKNOWN)

    def test_broken_device_symlink_returns_sentinel(self):
        iface_path = os.path.join(self.tmp, 'eth4')
        os.mkdir(iface_path)
        os.symlink(os.path.join(self.devices_root, 'does-not-exist'),
                    os.path.join(iface_path, 'device'))
        self.assertEqual(resolver.pcie_distance('eth4', self.tmp),
                          resolver.PCIE_DISTANCE_UNKNOWN)

    def test_no_pci_segment_at_all_returns_sentinel(self):
        # resolved path has no PCI BDF component at all
        self._make_iface_pointing_at('eth5', 'usb1', '1-1', '1-1:1.0')
        self.assertEqual(resolver.pcie_distance('eth5', self.tmp),
                          resolver.PCIE_DISTANCE_UNKNOWN)

    def test_usb_nic_behind_its_controller_is_not_a_sentinel(self):
        # a real USB NIC resolves THROUGH the xHCI controller, so it has a
        # perfectly ordinary hop-count - the sentinel above is rarer than
        # it looks, which is why the address tie-break matters here too.
        self._make_iface_pointing_at(
            'eth6', 'pci0000:00', '0000:00:14.0', 'usb1', '1-1', '1-1:1.0')
        self.assertEqual(resolver.pcie_distance('eth6', self.tmp), 1)


class TestPcieAddress(unittest.TestCase):
    """Hop depth alone ties for every NIC on the same bus - the normal
    case in a VM, where the hypervisor allocates one slot per attached
    NIC off the same root bus. The field report was exactly that: two
    virtio NICs at equal depth, ordered by raw MAC magnitude, which
    reversed the hypervisor's slot order and put each configured address
    on the wrong physical wire. The full bus address is what breaks that
    tie correctly.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.devices_root = os.path.join(self.tmp, 'devices')
        os.makedirs(self.devices_root)

    def _make_iface_pointing_at(self, name, *path_segments):
        target = os.path.join(self.devices_root, *path_segments)
        os.makedirs(target, exist_ok=True)
        iface_path = os.path.join(self.tmp, name)
        os.mkdir(iface_path)
        os.symlink(target, os.path.join(iface_path, 'device'))

    def test_shallow_device_is_its_own_bdf(self):
        self._make_iface_pointing_at('eth0', 'pci0000:00', '0000:00:1f.6')
        self.assertEqual(resolver.pcie_address('eth0', self.tmp),
                          ((0, 0, 0x1f, 6),))

    def test_deep_device_keeps_the_whole_path_root_first(self):
        self._make_iface_pointing_at(
            'eth1', 'pci0000:00', '0000:00:1c.0',
            '0000:01:00.0', '0000:02:04.0')
        self.assertEqual(resolver.pcie_address('eth1', self.tmp),
                          ((0, 0, 0x1c, 0), (0, 1, 0, 0), (0, 2, 4, 0)))

    def test_virtio_indirection_skipped_like_pcie_distance(self):
        self._make_iface_pointing_at(
            'eth2', 'pci0000:00', '0000:00:12.0', 'virtio2', 'net')
        self.assertEqual(resolver.pcie_address('eth2', self.tmp),
                          ((0, 0, 0x12, 0),))

    def test_same_slot_orders_by_pci_slot_number(self):
        # the reported shape: two NICs on the same bus, different slots
        self._make_iface_pointing_at('ethA', 'pci0000:00', '0000:00:05.0')
        self._make_iface_pointing_at('ethB', 'pci0000:00', '0000:00:06.0')
        self.assertLess(resolver.pcie_address('ethA', self.tmp),
                         resolver.pcie_address('ethB', self.tmp))

    def test_multifunction_siblings_order_by_function(self):
        # a dual-port card: port 0 must come before port 1, and hop count
        # cannot tell them apart at all
        self._make_iface_pointing_at(
            'ethC', 'pci0000:00', '0000:00:1c.0', '0000:03:00.0')
        self._make_iface_pointing_at(
            'ethD', 'pci0000:00', '0000:00:1c.0', '0000:03:00.1')
        self.assertEqual(resolver.pcie_distance('ethC', self.tmp),
                          resolver.pcie_distance('ethD', self.tmp))
        self.assertLess(resolver.pcie_address('ethC', self.tmp),
                         resolver.pcie_address('ethD', self.tmp))

    def test_missing_device_symlink_returns_sentinel(self):
        os.mkdir(os.path.join(self.tmp, 'eth3'))
        self.assertEqual(resolver.pcie_address('eth3', self.tmp),
                          resolver.PCIE_ADDRESS_UNKNOWN)

    def test_broken_device_symlink_returns_sentinel(self):
        iface_path = os.path.join(self.tmp, 'eth4')
        os.mkdir(iface_path)
        os.symlink(os.path.join(self.devices_root, 'does-not-exist'),
                    os.path.join(iface_path, 'device'))
        self.assertEqual(resolver.pcie_address('eth4', self.tmp),
                          resolver.PCIE_ADDRESS_UNKNOWN)

    def test_sentinel_sorts_after_every_real_address(self):
        # it must not be the empty tuple, which would sort FIRST
        self._make_iface_pointing_at('eth5', 'pci0000:00', '0000:00:1f.6')
        self.assertLess(resolver.pcie_address('eth5', self.tmp),
                         resolver.PCIE_ADDRESS_UNKNOWN)


class TestCanonicalSortKey(unittest.TestCase):
    """One canonical hardware order, shared by ordinary bootstrap naming
    and by pending-node pairing - if they disagreed, a name assigned by
    one would contradict the other.
    """

    def test_distance_still_leads_over_address(self):
        # an onboard NIC deep in the bus address space must still beat an
        # add-in card behind a bridge, whatever their addresses look like
        with mock.patch.object(resolver, 'pcie_distance',
                                side_effect=lambda n: {'a': 1, 'b': 2}[n]), \
             mock.patch.object(resolver, 'pcie_address',
                                side_effect=lambda n: {'a': ((0, 0, 0x1f, 6),),
                                                        'b': ((0, 0, 1, 0),)}[n]):
            self.assertLess(resolver.canonical_sort_key('zz', 'a'),
                             resolver.canonical_sort_key('aa', 'b'))

    def test_address_beats_mac_magnitude_at_equal_distance(self):
        with mock.patch.object(resolver, 'pcie_distance', return_value=1), \
             mock.patch.object(resolver, 'pcie_address',
                                side_effect=lambda n: {'a': ((0, 0, 5, 0),),
                                                        'b': ((0, 0, 6, 0),)}[n]):
            # 'a' has the numerically HIGHER mac but the lower slot
            self.assertLess(resolver.canonical_sort_key('ff:ff', 'a'),
                             resolver.canonical_sort_key('00:00', 'b'))

    def test_mac_is_the_last_resort_tie_break(self):
        with mock.patch.object(resolver, 'pcie_distance', return_value=1), \
             mock.patch.object(resolver, 'pcie_address',
                                return_value=resolver.PCIE_ADDRESS_UNKNOWN):
            self.assertLess(resolver.canonical_sort_key('aa', 'x'),
                             resolver.canonical_sort_key('bb', 'y'))


class TestNodeNameOrder(unittest.TestCase):
    """Pending node names are paired with hardware in index order, which
    has to be numeric - a plain sort puts 'eth10' before 'eth2'.
    """

    def test_numeric_not_lexical(self):
        self.assertEqual(sorted(['eth10', 'eth2', 'eth1'],
                                 key=resolver.node_name_order),
                          ['eth1', 'eth2', 'eth10'])

    def test_name_without_index_sorts_last(self):
        self.assertEqual(sorted(['eth1', 'lan'],
                                 key=resolver.node_name_order),
                          ['eth1', 'lan'])
        self.assertEqual(sorted(['lan', 'eth9'],
                                 key=resolver.node_name_order),
                          ['eth9', 'lan'])


class TestComputeBootstrapPlan(unittest.TestCase):
    """Bootstrap naming is what makes a box's very first boot (before any
    hw-id exists) deterministic, the same way hw-id makes every boot after
    that deterministic - it must depend only on PCIe topology and MAC
    rank, never on whatever name the racy cosmetic fast-path happened to
    assign. pcie_distance is held constant by default in these tests, so
    they exercise pure MAC-rank ordering (see TestPcieDistance for the
    topology-ordering cases specifically).
    """

    def setUp(self):
        patcher = mock.patch.object(resolver, 'is_wireless_interface',
                                     return_value=False)
        self.is_wireless = patcher.start()
        self.addCleanup(patcher.stop)

        distance_patcher = mock.patch.object(resolver, 'pcie_distance',
                                              return_value=0)
        self.pcie_distance = distance_patcher.start()
        self.addCleanup(distance_patcher.stop)

        # the fake names below ('eth0', 'eth1', ...) exist for real on some
        # build hosts - without this, pcie_address() would resolve the
        # host's own sysfs for those and the sentinel for the rest, making
        # the canonical order host-dependent. Pinned to the sentinel so
        # these tests keep exercising pure MAC-rank ordering.
        address_patcher = mock.patch.object(
            resolver, 'pcie_address',
            return_value=resolver.PCIE_ADDRESS_UNKNOWN)
        self.pcie_address = address_patcher.start()
        self.addCleanup(address_patcher.stop)

    def test_equal_distance_orders_by_pci_slot_not_mac_magnitude(self):
        # the reported silent-swap shape, at the bootstrap-naming layer:
        # both NICs sit at the same depth, so MAC rank used to decide -
        # the lower slot must win regardless of MAC magnitude.
        self.pcie_address.side_effect = lambda name: {
            'ethA': ((0, 0, 5, 0),),
            'ethB': ((0, 0, 6, 0),),
        }[name]
        current = {'ethB': '52:54:00:00:00:22', 'ethA': '52:54:00:ff:00:21'}
        plan = resolver.compute_bootstrap_plan({}, current, {})
        self.assertEqual(plan, {'ethA': 'eth0', 'ethB': 'eth1'})

    def test_distance_still_beats_pci_address(self):
        self.pcie_distance.side_effect = lambda name: {'ethA': 2, 'ethB': 1}[name]
        self.pcie_address.side_effect = lambda name: {
            'ethA': ((0, 0, 5, 0),),
            'ethB': ((0, 0, 6, 0),),
        }[name]
        current = {'ethA': 'aa', 'ethB': 'bb'}
        plan = resolver.compute_bootstrap_plan({}, current, {})
        self.assertEqual(plan, {'ethB': 'eth0', 'ethA': 'eth1'})

    def test_sorted_by_mac_independent_of_current_names(self):
        # names are in the OPPOSITE order of their MACs
        current = {'eth5': 'bb', 'eth2': 'aa'}
        plan = resolver.compute_bootstrap_plan({}, current, {})
        self.assertEqual(plan, {'eth2': 'eth0', 'eth5': 'eth1'})

    def test_noop_when_already_in_canonical_rank_order(self):
        current = {'eth0': 'aa', 'eth1': 'bb'}
        plan = resolver.compute_bootstrap_plan({}, current, {})
        self.assertEqual(plan, {})

    def test_configured_targets_are_never_overwritten(self):
        configured = {'m0': 'eth0'}
        current = {'eth0': 'm0', 'eth9': 'm2', 'eth8': 'm1'}
        plan = resolver.compute_bootstrap_plan(configured, current, {})
        self.assertNotIn('eth0', plan.values())
        self.assertEqual(plan.get('eth8'), 'eth1')
        self.assertEqual(plan.get('eth9'), 'eth2')

    def test_new_interface_backfills_a_gap_with_no_pending_node(self):
        # eth1 is a gap between two hw-id'd interfaces, but nothing in
        # config.boot reserves it (no hw-id, no pending node either - the
        # interface was fully deleted at some point, or never existed) -
        # a new, unrelated NIC discovered this boot is free to take it,
        # the same as it would on a system with no config for it at all.
        configured = {'m0': 'eth0', 'm2': 'eth2'}
        current = {'eth0': 'm0', 'eth2': 'm2', 'eth9': 'new-mac'}
        plan = resolver.compute_bootstrap_plan(configured, current, {})
        self.assertEqual(plan, {'eth9': 'eth1'})

    def test_multiple_new_interfaces_backfill_gaps_in_order(self):
        configured = {'m0': 'eth0', 'm2': 'eth2'}
        current = {
            'eth0': 'm0', 'eth2': 'm2',
            'ethB': 'bb', 'ethA': 'aa',
        }
        plan = resolver.compute_bootstrap_plan(configured, current, {})
        # lower mac 'aa' takes the gap at eth1 first, 'bb' continues to
        # the next free slot, eth3 - not "skip past the gap to eth3/eth4"
        self.assertEqual(plan, {'ethA': 'eth1', 'ethB': 'eth3'})

    def test_ethernet_and_wireless_numbered_independently(self):
        self.is_wireless.side_effect = lambda name: name == 'radio0'
        current = {'ifaceB': 'bb', 'radio0': 'aa'}
        plan = resolver.compute_bootstrap_plan({}, current, {})
        self.assertEqual(plan.get('radio0'), 'wlan0')
        self.assertEqual(plan.get('ifaceB'), 'eth0')

    def test_squatter_already_in_existing_plan_excluded(self):
        # 'eth0' is a squatter the hw-id plan already decided to move away
        # (existing_plan key) - it IS still bootstrap candidacy (see
        # unmatched_candidates()), but must never be handed a second,
        # conflicting assignment on top of its existing_plan eviction.
        existing_plan = {'eth0': 'eth3'}
        current = {'eth0': 'unconfigured-mac', 'eth7': 'm0'}
        plan = resolver.compute_bootstrap_plan({'m0': 'eth1'}, current,
                                                existing_plan)
        self.assertNotIn('eth0', plan)

    def test_bootstrap_targets_never_collide_with_existing_plan_values(self):
        # existing_plan says an interface currently named 'oldname' is
        # moving to 'eth0' - nothing else in `current` is named 'eth0' or
        # 'eth*' at all, so if that target isn't reserved, find_available()
        # would freely hand 'eth0' to the bootstrap candidate too.
        existing_plan = {'oldname': 'eth0'}
        current = {'oldname': 'm0', 'newnic': 'unconfigured-mac'}
        plan = resolver.compute_bootstrap_plan({'m0': 'eth0'}, current,
                                                existing_plan)
        self.assertNotEqual(plan.get('newnic'), 'eth0')

    def test_smaller_pcie_distance_wins_over_higher_mac(self):
        # 'bb' has the numerically higher MAC but sits closer to the root
        # complex - it must be named first despite losing on MAC alone.
        current = {'eth5': 'bb', 'eth2': 'aa'}
        self.pcie_distance.side_effect = lambda name: {'eth5': 0, 'eth2': 3}[name]
        plan = resolver.compute_bootstrap_plan({}, current, {})
        self.assertEqual(plan, {'eth5': 'eth0', 'eth2': 'eth1'})

    def test_same_pcie_distance_falls_back_to_mac_order(self):
        current = {'eth5': 'bb', 'eth2': 'aa'}
        self.pcie_distance.side_effect = lambda name: 2  # tie for both
        plan = resolver.compute_bootstrap_plan({}, current, {})
        self.assertEqual(plan, {'eth2': 'eth0', 'eth5': 'eth1'})

    def test_unknown_pcie_distance_sorts_last(self):
        # 'aa' has the numerically lowest MAC but an undeterminable bus
        # position (e.g. a USB NIC) - it must not jump the queue.
        current = {'eth9': 'cc', 'eth5': 'bb', 'ethX': 'aa'}
        self.pcie_distance.side_effect = lambda name: {
            'eth9': 1, 'eth5': 2, 'ethX': resolver.PCIE_DISTANCE_UNKNOWN,
        }[name]
        plan = resolver.compute_bootstrap_plan({}, current, {})
        self.assertEqual(plan, {'eth9': 'eth0', 'eth5': 'eth1', 'ethX': 'eth2'})

    def test_pcie_distance_ordering_independent_of_ethernet_wireless_split(self):
        # distance-based ordering applies within each type group separately,
        # same as MAC does today - a wlan candidate's distance must not
        # affect eth numbering or vice versa.
        self.is_wireless.side_effect = lambda name: name == 'radio0'
        current = {'ifaceB': 'bb', 'radio0': 'aa'}
        self.pcie_distance.side_effect = lambda name: {
            'ifaceB': 5, 'radio0': 0,
        }[name]
        plan = resolver.compute_bootstrap_plan({}, current, {})
        self.assertEqual(plan.get('radio0'), 'wlan0')
        self.assertEqual(plan.get('ifaceB'), 'eth0')


class TestComputeBootstrapPlanGapFill(unittest.TestCase):
    """compute_bootstrap_plan() fills ordinary numeric gaps (no config
    trace at all) deterministically by PCIe distance then MAC. A pending
    node (hw-id deleted, node kept - see get_pending_hwid_nodes()) is a
    separate concern here: passing `pending` reserves its name so an
    unrelated candidate can never squat on it and inherit its settings -
    only match_pending_nodes() may fill it, and only when unambiguous.
    """

    def setUp(self):
        patcher = mock.patch.object(resolver, 'is_wireless_interface',
                                     return_value=False)
        self.is_wireless = patcher.start()
        self.addCleanup(patcher.stop)

        distance_patcher = mock.patch.object(resolver, 'pcie_distance',
                                              return_value=0)
        self.pcie_distance = distance_patcher.start()
        self.addCleanup(distance_patcher.stop)

        # the fake names below ('eth0', 'eth1', ...) exist for real on some
        # build hosts - without this, pcie_address() would resolve the
        # host's own sysfs for those and the sentinel for the rest, making
        # the canonical order host-dependent. Pinned to the sentinel so
        # these tests keep exercising pure MAC-rank ordering.
        address_patcher = mock.patch.object(
            resolver, 'pcie_address',
            return_value=resolver.PCIE_ADDRESS_UNKNOWN)
        self.pcie_address = address_patcher.start()
        self.addCleanup(address_patcher.stop)

    def test_open_name_filled_like_an_ordinary_gap(self):
        # 'eth1' has nothing configured for it and no pending reservation
        # - it is simply the lowest open name.
        configured = {'m0': 'eth0'}
        current = {'eth0': 'm0', 'eth9': 'new-mac'}
        plan = resolver.compute_bootstrap_plan(configured, current, {})
        self.assertEqual(plan.get('eth9'), 'eth1')

    def test_ascending_fill_has_no_preference_between_open_names(self):
        # two open names (eth1, eth4 - the reason either is open makes no
        # difference) and two candidates - the lower-sorted candidate
        # takes the lower-numbered open name, unconditionally.
        configured = {'m0': 'eth0', 'm2': 'eth2', 'm3': 'eth3'}
        current = {'eth0': 'm0', 'eth2': 'm2', 'eth3': 'm3',
                   'eth9': 'bb', 'eth8': 'aa'}
        plan = resolver.compute_bootstrap_plan(configured, current, {})
        self.assertEqual(plan.get('eth8'), 'eth1')
        self.assertEqual(plan.get('eth9'), 'eth4')

    def test_two_plain_gaps_fill_in_ascending_order(self):
        # two fully-deleted interfaces (no hw-id, no pending node either)
        # - both ordinary gaps, filled by the same ascending PCIe/MAC
        # sort as any other unconfigured hardware.
        configured = {
            '00:00:5e:00:53:00': 'eth0', '00:00:5e:00:53:01': 'eth1',
            '00:00:5e:00:53:03': 'eth3', '00:00:5e:00:53:05': 'eth5',
            '00:00:5e:00:53:06': 'eth6', '00:00:5e:00:53:07': 'eth7',
        }
        current = {name: mac for mac, name in configured.items()}
        current.update({'eth9': '00:00:5e:00:53:02',
                        'eth8': '00:00:5e:00:53:04'})
        plan = resolver.compute_bootstrap_plan(configured, current, {})
        self.assertEqual(plan.get('eth9'), 'eth2')
        self.assertEqual(plan.get('eth8'), 'eth4')

    def test_open_names_currently_squatted_by_a_rightful_mover_are_not_taken(self):
        # real boot reproduction (via the resolver's own status file,
        # captured mid-failure): the cosmetic fast-path this boot had
        # every configured mac sitting on some OTHER configured mac's
        # target name (a full rotation), including the two plain gaps
        # (eth1, eth6) both currently squatted by macs that are about to
        # move elsewhere via a rightful-owner move. existing_plan's
        # SOURCE names looked "taken" at the exact moment this function
        # ran, but safe_bulk_rename()'s two-phase staging vacates every
        # source before any target is claimed - so they must not count
        # as taken, or the two real candidates get needlessly pushed to
        # fresh eth8/eth9-style slots instead of their own open names.
        configured = {
            '00:00:5e:00:53:00': 'eth0', '00:00:5e:00:53:02': 'eth2',
            '00:00:5e:00:53:03': 'eth3', '00:00:5e:00:53:04': 'eth4',
            '00:00:5e:00:53:05': 'eth5', '00:00:5e:00:53:07': 'eth7',
        }
        current = {
            'eth4': '00:00:5e:00:53:00', 'eth6': '00:00:5e:00:53:02',
            'eth7': '00:00:5e:00:53:03', 'eth2': '00:00:5e:00:53:04',
            'eth3': '00:00:5e:00:53:05', 'eth1': '00:00:5e:00:53:07',
            'eth0': '00:00:5e:00:53:06',  # unconfigured - squats on eth0
            'eth5': '00:00:5e:00:53:01',  # unconfigured - squats on eth5
        }
        existing_plan = resolver.compute_rename_plan(configured, current)
        plan = resolver.compute_bootstrap_plan(configured, current,
                                                existing_plan)
        self.assertEqual(plan.get('eth5'), 'eth1')
        self.assertEqual(plan.get('eth0'), 'eth6')

    def test_pending_name_reserved_against_unrelated_bootstrap_candidate(self):
        # 'eth1' is pending (no hw-id) on a box that already has an
        # established ethernet baseline (eth0's own hw-id) - two unrelated
        # new NICs discovered this boot must not land on it just because
        # sequential numbering would otherwise reach it as the second
        # assignment.
        configured = {'m0': 'eth0'}
        pending = {'ethernet': {'eth1'}, 'wireless': set()}
        current = {'eth0': 'm0', 'eth9': 'aa', 'eth8': 'bb'}
        plan = resolver.compute_bootstrap_plan(configured, current, {},
                                                pending=pending)
        self.assertEqual(plan.get('eth9'), 'eth2')
        self.assertEqual(plan.get('eth8'), 'eth3')
        self.assertNotEqual(plan.get('eth9'), 'eth1')
        self.assertNotEqual(plan.get('eth8'), 'eth1')

    def test_pending_name_not_reserved_with_no_established_baseline(self):
        # 'eth0' is pending (e.g. a cloud-init/first-boot script wrote it
        # into config.boot before this script ever ran) on a box that has
        # NEVER bound a real ethernet hw-id - there is no established
        # mapping to protect, so it is just another open slot and
        # competes for it like any other unconfigured candidate, exactly
        # as it would if `pending` had not been passed at all.
        configured = {}
        pending = {'ethernet': {'eth0'}, 'wireless': set()}
        current = {'eth9': 'aa', 'eth8': 'bb'}
        plan = resolver.compute_bootstrap_plan(configured, current, {},
                                                pending=pending)
        self.assertEqual(plan.get('eth9'), 'eth0')
        self.assertEqual(plan.get('eth8'), 'eth1')

    def test_pending_name_reserved_if_baseline_exists_for_other_type(self):
        # an established WIRELESS baseline must not protect a pending
        # ETHERNET node - the two type groups are judged independently.
        configured = {'w0': 'wlan0'}
        pending = {'ethernet': {'eth0'}, 'wireless': set()}
        current = {'eth9': 'aa', 'eth8': 'bb'}
        plan = resolver.compute_bootstrap_plan(configured, current, {},
                                                pending=pending)
        self.assertEqual(plan.get('eth9'), 'eth0')
        self.assertEqual(plan.get('eth8'), 'eth1')

    def test_reclaimed_candidate_excluded_from_ordinary_bootstrap(self):
        # main() already matched this candidate to a pending node via
        # match_pending_nodes() - it must not also be assigned a fresh
        # bootstrap name here, even if its current name differs from the
        # reclaimed target (main() handles the actual rename itself).
        configured = {}
        current = {'eth9': 'm1', 'eth8': 'm2'}
        plan = resolver.compute_bootstrap_plan(configured, current, {},
                                                reclaimed={'m1': 'eth1'})
        self.assertNotIn('eth9', plan)
        self.assertIn('eth8', plan)


class TestSafeBulkRename(unittest.TestCase):
    """The two-phase rename must accurately report what actually happened -
    a phase-2 (scratch -> final target) failure must not be reported as a
    successful rename, and must not leave the interface down indefinitely
    under a name nothing else knows about.
    """

    def setUp(self):
        patcher = mock.patch.object(resolver, 'get_ifindex',
                                     side_effect=lambda name: name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_all_renames_succeed(self):
        with mock.patch.object(resolver, 'run', return_value=0):
            applied = resolver.safe_bulk_rename({'eth5': 'eth0'})
        self.assertEqual(applied, {'eth5': 'eth0'})

    def test_phase_two_failure_is_not_reported_as_applied(self):
        # 'ip link set dev vyetheth5 name eth0' fails (exit 1); everything
        # else (down, the phase-1 rename to scratch) succeeds
        def fake_run(command, *_a, **_kw):
            return 1 if command == 'ip link set dev vyetheth5 name eth0' else 0

        with mock.patch.object(resolver, 'run', side_effect=fake_run):
            applied = resolver.safe_bulk_rename({'eth5': 'eth0'})

        self.assertNotIn('eth5', applied)
        self.assertNotEqual(applied.get('eth5'), 'eth0')

    def test_phase_two_failure_brings_scratch_name_back_up(self):
        calls = []

        def fake_run(command, *_a, **_kw):
            calls.append(command)
            return 1 if command == 'ip link set dev vyetheth5 name eth0' else 0

        with mock.patch.object(resolver, 'run', side_effect=fake_run):
            resolver.safe_bulk_rename({'eth5': 'eth0'})

        self.assertIn('ip link set dev vyetheth5 up', calls)
        self.assertNotIn('ip link set dev eth0 up', calls)

    def test_one_failure_does_not_affect_other_renames_in_the_batch(self):
        def fake_run(command, *_a, **_kw):
            return 1 if command == 'ip link set dev vyetheth5 name eth0' else 0

        with mock.patch.object(resolver, 'run', side_effect=fake_run):
            applied = resolver.safe_bulk_rename({'eth5': 'eth0', 'eth9': 'eth1'})

        self.assertNotIn('eth5', applied)
        self.assertEqual(applied.get('eth9'), 'eth1')


class TestGetPermanentMac(unittest.TestCase):
    """Part of the original race is reading a MAC before the driver has
    programmed the permanent address. Verify the ethtool-first,
    sysfs-fallback behaviour, including drivers that report an all-zero
    'unsupported' permanent address instead of failing outright.
    """

    def test_ethtool_permanent_address(self):
        with mock.patch.object(
                resolver, 'rc_cmd',
                return_value=(0, 'Permanent address: aa:bb:cc:dd:ee:ff\n')):
            self.assertEqual(resolver.get_permanent_mac('eth0'),
                              'aa:bb:cc:dd:ee:ff')

    def test_ethtool_zero_address_falls_back_to_sysfs(self):
        with mock.patch.object(
                resolver, 'rc_cmd',
                return_value=(0, 'Permanent address: 00:00:00:00:00:00\n')), \
             mock.patch('pathlib.Path.read_text',
                        return_value='11:22:33:44:55:66\n'):
            self.assertEqual(resolver.get_permanent_mac('eth0'),
                              '11:22:33:44:55:66')

    def test_ethtool_unsupported_falls_back_to_sysfs(self):
        with mock.patch.object(
                resolver, 'rc_cmd',
                return_value=(1, 'Operation not supported')), \
             mock.patch('pathlib.Path.read_text',
                        return_value='11:22:33:44:55:66\n'):
            self.assertEqual(resolver.get_permanent_mac('eth0'),
                              '11:22:33:44:55:66')

    def test_no_mac_available_returns_empty(self):
        with mock.patch.object(resolver, 'rc_cmd', return_value=(1, '')), \
             mock.patch('pathlib.Path.read_text', side_effect=OSError):
            self.assertEqual(resolver.get_permanent_mac('eth0'), '')


class TestDiscoverPhysicalInterfaces(unittest.TestCase):
    """Only interfaces with a real bus 'device' link are candidates -
    bridges/bonds/VLANs/veth must be excluded regardless of name, since
    this replaces the racy udev DRIVERS=="?*" check with a stable,
    post-settle sysfs read.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        def make_iface(name, mac=None, has_device=True):
            path = os.path.join(self.tmp, name)
            os.mkdir(path)
            if has_device:
                os.mkdir(os.path.join(path, 'device'))
            if mac:
                with open(os.path.join(path, 'address'), 'w') as f:
                    f.write(mac + '\n')

        make_iface('eth0', mac='aa:aa:aa:aa:aa:00')
        make_iface('eth1', mac='aa:aa:aa:aa:aa:01')
        make_iface('br0', mac='aa:aa:aa:aa:aa:99', has_device=False)
        make_iface('lo', has_device=False)

    def test_only_physical_interfaces_with_mac(self):
        with mock.patch.object(resolver, 'rc_cmd', return_value=(1, '')):
            found = resolver.discover_physical_interfaces(self.tmp)
        self.assertEqual(found, {
            'eth0': 'aa:aa:aa:aa:aa:00',
            'eth1': 'aa:aa:aa:aa:aa:01',
        })
        self.assertNotIn('br0', found)
        self.assertNotIn('lo', found)


class TestSyncRescanHints(unittest.TestCase):
    """New/unconfigured hardware must still be surfaced to
    vyos-interface-rescan.py, already-configured interfaces must not, and
    hints left under a pre-rename name must not linger once the resolver
    has moved that interface to its hw-id target.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self._orig_dir = resolver.vyos_udev_dir
        resolver.vyos_udev_dir = self.tmp
        self.addCleanup(setattr, resolver, 'vyos_udev_dir', self._orig_dir)

    def test_writes_hint_for_unconfigured_interface(self):
        resolver.sync_rescan_hints({'eth5': 'new-mac'}, configured={})
        hint = os.path.join(self.tmp, 'eth5')
        self.assertTrue(os.path.isfile(hint))
        with open(hint) as f:
            self.assertEqual(f.read(), 'new-mac')

    def test_no_hint_for_configured_interface(self):
        resolver.sync_rescan_hints({'eth0': 'm0'}, configured={'m0': 'eth0'})
        self.assertFalse(os.path.exists(os.path.join(self.tmp, 'eth0')))

    def test_stale_hint_removed_after_rename(self):
        # udev's cosmetic fast-path wrote a hint under the pre-rename name;
        # the resolver then moved that interface to its hw-id target.
        stale = os.path.join(self.tmp, 'eth7')
        with open(stale, 'w') as f:
            f.write('m2')
        resolver.sync_rescan_hints({'eth10': 'm2'}, configured={'m2': 'eth10'},
                                    stale_names={'eth7'})
        self.assertFalse(os.path.exists(stale))



class TestMainFirstBootBootstrap(unittest.TestCase):
    """Direct regression guard for the gap this feature closes: main()
    used to leave a fully-unconfigured system's interfaces at whatever
    racy cosmetic name they already had, with no settle wait at all, and
    freeze that into the rescan hints vyos-interface-rescan.py persists.
    """

    def setUp(self):
        self.udev_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.udev_dir, ignore_errors=True)
        self._orig_udev_dir = resolver.vyos_udev_dir
        resolver.vyos_udev_dir = self.udev_dir
        self.addCleanup(setattr, resolver, 'vyos_udev_dir', self._orig_udev_dir)

        status_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, status_dir, ignore_errors=True)
        self._orig_status_file = resolver.status_file
        resolver.status_file = resolver.Path(status_dir) / 'status.json'
        self.addCleanup(setattr, resolver, 'status_file', self._orig_status_file)

    def test_empty_configfile_bootstrap_renames_and_hints_new_names(self):
        # a tiny fake kernel: name -> mac, mutated by simulated 'ip link'
        # calls so discover_physical_interfaces() reflects renames for real
        state = {'eth5': 'bb', 'eth2': 'aa'}  # cosmetic fast-path leftover

        def fake_discover(*_a, **_kw):
            return dict(state)

        def fake_run(command, *_a, **_kw):
            parts = command.split()
            if 'name' in parts:
                old = parts[parts.index('dev') + 1]
                new = parts[parts.index('name') + 1]
                if old in state:
                    state[new] = state.pop(old)
            return 0

        with mock.patch.object(resolver, 'get_configfile_interfaces',
                                return_value={}), \
             mock.patch.object(resolver, 'get_pending_hwid_nodes',
                                return_value={'ethernet': set(), 'wireless': set()}), \
             mock.patch.object(resolver, 'discover_physical_interfaces',
                                side_effect=fake_discover), \
             mock.patch.object(resolver, 'is_wireless_interface',
                                return_value=False), \
             mock.patch.object(resolver, 'run', side_effect=fake_run), \
             mock.patch('time.sleep'):
            resolver.main()

        hints = set(os.listdir(self.udev_dir))
        # renamed into MAC-rank order: lower mac 'aa' -> eth0, higher 'bb' -> eth1
        self.assertEqual(hints, {'eth0', 'eth1'})
        with open(os.path.join(self.udev_dir, 'eth0')) as f:
            self.assertEqual(f.read(), 'aa')
        with open(os.path.join(self.udev_dir, 'eth1')) as f:
            self.assertEqual(f.read(), 'bb')

    def test_pending_node_still_settles_when_its_hardware_is_slow_to_appear(self):
        # field report: a pending node ended up permanently bound to a
        # fresh eth8/eth9-style name despite its own hardware genuinely
        # being present - because that hardware (a slower driver, exactly
        # the multi-vendor-NIC race this whole feature addresses) simply
        # had not shown up in the FIRST, unsettled discover_physical_
        # interfaces() snapshot wait_for_hardware() returns as soon as all
        # already-CONFIGURED macs are found. Since that snapshot showed
        # nothing unconfigured yet, main()'s gate into wait_for_settle()
        # never even ran, giving the slow hardware zero extra time to
        # appear before the boot gave up. A pending node in play must
        # force wait_for_settle() to run regardless of what the early
        # snapshot shows, so slower hardware still gets its chance.
        configured = {'m0': 'eth0'}
        pending = {'ethernet': {'eth1'}, 'wireless': set()}

        calls = {'n': 0}

        def fake_discover(*_a, **_kw):
            calls['n'] += 1
            if calls['n'] <= 2:
                return {'eth0': 'm0'}  # m1's hardware not visible yet
            return {'eth0': 'm0', 'eth9': 'm1'}  # now it has appeared

        state = {'eth0': 'm0', 'eth9': 'm1'}

        def fake_run(command, *_a, **_kw):
            parts = command.split()
            if 'name' in parts:
                old = parts[parts.index('dev') + 1]
                new = parts[parts.index('name') + 1]
                if old in state:
                    state[new] = state.pop(old)
            return 0

        with mock.patch.object(resolver, 'get_configfile_interfaces',
                                return_value=configured), \
             mock.patch.object(resolver, 'get_pending_hwid_nodes',
                                return_value=pending), \
             mock.patch.object(resolver, 'discover_physical_interfaces',
                                side_effect=fake_discover), \
             mock.patch.object(resolver, 'is_wireless_interface',
                                return_value=False), \
             mock.patch.object(resolver, 'pcie_distance', return_value=0), \
             mock.patch.object(
                 resolver, 'pcie_address',
                 return_value=resolver.PCIE_ADDRESS_UNKNOWN), \
             mock.patch.object(resolver, 'run', side_effect=fake_run), \
             mock.patch('time.sleep'):
            resolver.main()

        self.assertEqual(state.get('eth1'), 'm1')

        status = json.loads(resolver.status_file.read_text())
        self.assertEqual(status['reclaimed'], {'m1': 'eth1'})
        self.assertEqual(status['pending_unresolved'], [])

    def test_reported_reproduction_end_to_end(self):
        # exact reported scenario: eth0/eth2 keep their hw-id, eth1's hw-id
        # was deleted (the documented "NIC replaced" remediation) but its
        # node - and an address setting - stay in config.boot. The same
        # physical NIC (mac 'm1') must come back as 'eth1', not bootstrap
        # past the floor to 'eth3', and must still get a rescan hint under
        # 'eth1' so vyos-interface-rescan.py can refill its hw-id.
        configured = {'m0': 'eth0', 'm2': 'eth2'}
        pending = {'ethernet': {'eth1'}, 'wireless': set()}
        # cosmetic fast-path already placed everything at its final
        # hw-id'd name except the replaced NIC, which landed on a racy name
        state = {'eth0': 'm0', 'eth2': 'm2', 'eth9': 'm1'}

        def fake_discover(*_a, **_kw):
            return dict(state)

        def fake_run(command, *_a, **_kw):
            parts = command.split()
            if 'name' in parts:
                old = parts[parts.index('dev') + 1]
                new = parts[parts.index('name') + 1]
                if old in state:
                    state[new] = state.pop(old)
            return 0

        with mock.patch.object(resolver, 'get_configfile_interfaces',
                                return_value=configured), \
             mock.patch.object(resolver, 'get_pending_hwid_nodes',
                                return_value=pending), \
             mock.patch.object(resolver, 'discover_physical_interfaces',
                                side_effect=fake_discover), \
             mock.patch.object(resolver, 'is_wireless_interface',
                                return_value=False), \
             mock.patch.object(resolver, 'run', side_effect=fake_run), \
             mock.patch('time.sleep'):
            resolver.main()

        # the NIC is back at 'eth1', not bootstrapped past the floor to 'eth3'
        self.assertEqual(state.get('eth1'), 'm1')
        self.assertNotIn('eth3', state)

        # still gets a rescan hint under its reclaimed name, so
        # vyos-interface-rescan.py can write the real hw-id into the
        # existing 'eth1' node (preserving its other settings, e.g. address)
        hints = set(os.listdir(self.udev_dir))
        self.assertEqual(hints, {'eth1'})
        with open(os.path.join(self.udev_dir, 'eth1')) as f:
            self.assertEqual(f.read(), 'm1')

        status = json.loads(resolver.status_file.read_text())
        self.assertEqual(status['reclaimed'], {'m1': 'eth1'})
        self.assertEqual(status['pending_unresolved'], [])

    def test_fully_deleted_interfaces_backfill_their_gaps_end_to_end(self):
        # reported scenario: eth3, eth6 and eth7 were fully deleted (not
        # just their hw-id - the whole node, so get_pending_hwid_nodes()
        # has nothing for them either) while eth0,1,2,4,5,8,9 stay
        # configured. The three now-unconfigured NICs must backfill the
        # gaps at 3/6/7 in MAC order, not bootstrap past the highest
        # configured index (9) to 10/11/12.
        configured = {
            'm0': 'eth0', 'm1': 'eth1', 'm2': 'eth2', 'm4': 'eth4',
            'm5': 'eth5', 'm8': 'eth8', 'm9': 'eth9',
        }
        pending = {'ethernet': set(), 'wireless': set()}
        state = {name: mac for mac, name in configured.items()}
        # realistic macs, deliberately NOT alphabetically matching their
        # old slot, so the test can't pass by coincidence
        state.update({'ethX': 'ff:ff:ff:ff:ff:07',
                       'ethY': 'aa:aa:aa:aa:aa:03',
                       'ethZ': 'cc:cc:cc:cc:cc:06'})

        def fake_discover(*_a, **_kw):
            return dict(state)

        def fake_run(command, *_a, **_kw):
            parts = command.split()
            if 'name' in parts:
                old = parts[parts.index('dev') + 1]
                new = parts[parts.index('name') + 1]
                if old in state:
                    state[new] = state.pop(old)
            return 0

        with mock.patch.object(resolver, 'get_configfile_interfaces',
                                return_value=configured), \
             mock.patch.object(resolver, 'get_pending_hwid_nodes',
                                return_value=pending), \
             mock.patch.object(resolver, 'discover_physical_interfaces',
                                side_effect=fake_discover), \
             mock.patch.object(resolver, 'is_wireless_interface',
                                return_value=False), \
             mock.patch.object(resolver, 'pcie_distance', return_value=0), \
             mock.patch.object(
                 resolver, 'pcie_address',
                 return_value=resolver.PCIE_ADDRESS_UNKNOWN), \
             mock.patch.object(resolver, 'run', side_effect=fake_run), \
             mock.patch('time.sleep'):
            resolver.main()

        # the three gaps got backfilled in ascending MAC order, not pushed
        # past the highest configured index to eth10/eth11/eth12
        self.assertEqual(state.get('eth3'), 'aa:aa:aa:aa:aa:03')
        self.assertEqual(state.get('eth6'), 'cc:cc:cc:cc:cc:06')
        self.assertEqual(state.get('eth7'), 'ff:ff:ff:ff:ff:07')
        self.assertNotIn('eth10', state)
        self.assertNotIn('eth11', state)
        self.assertNotIn('eth12', state)

    def test_stray_leftover_interface_makes_reclaim_ambiguous(self):
        # field report: deleting only eth7's hw-id and rebooting produced
        # "could not be safely auto-matched" instead of a clean reclaim,
        # because a stray interface left over from an earlier, unrelated
        # boot (e.g. a scratch vyethN name stuck after a failed rename)
        # was also present, making this a 1 pending/2 candidate case.
        # There is no way to tell which candidate was "really" eth7's own
        # past hardware once its hw-id is gone, so eth7 stays unresolved;
        # both candidates still get a real, settings-free hw-id via
        # ordinary bootstrap naming instead of being lost.
        configured = {
            'm0': 'eth0', 'm1': 'eth1', 'm2': 'eth2', 'm4': 'eth4',
            'm5': 'eth5', 'm6': 'eth6',
        }
        pending = {'ethernet': {'eth7'}, 'wireless': set()}
        state = {name: mac for mac, name in configured.items()}
        state.update({'eth9': 'aa:bb:cc:dd:ee:07',      # eth7's own hardware
                      'vyeth13': 'ff:ff:ff:ff:ff:99'})  # unrelated leftover

        def fake_discover(*_a, **_kw):
            return dict(state)

        def fake_run(command, *_a, **_kw):
            parts = command.split()
            if 'name' in parts:
                old = parts[parts.index('dev') + 1]
                new = parts[parts.index('name') + 1]
                if old in state:
                    state[new] = state.pop(old)
            return 0

        with mock.patch.object(resolver, 'get_configfile_interfaces',
                                return_value=configured), \
             mock.patch.object(resolver, 'get_pending_hwid_nodes',
                                return_value=pending), \
             mock.patch.object(resolver, 'discover_physical_interfaces',
                                side_effect=fake_discover), \
             mock.patch.object(resolver, 'is_wireless_interface',
                                return_value=False), \
             mock.patch.object(resolver, 'pcie_distance', return_value=0), \
             mock.patch.object(
                 resolver, 'pcie_address',
                 return_value=resolver.PCIE_ADDRESS_UNKNOWN), \
             mock.patch.object(resolver, 'run', side_effect=fake_run), \
             mock.patch('time.sleep'):
            resolver.main()

        # 'eth7' stays pending rather than being guessed at; both
        # candidates still land on real, settings-free names (the lone
        # ordinary gap, then the next fresh slot after that)
        self.assertNotIn('eth7', state)
        self.assertEqual(state.get('eth3'), 'aa:bb:cc:dd:ee:07')
        self.assertEqual(state.get('eth8'), 'ff:ff:ff:ff:ff:99')

        hints = set(os.listdir(self.udev_dir))
        self.assertEqual(hints, {'eth3', 'eth8'})

        status = json.loads(resolver.status_file.read_text())
        self.assertEqual(status['pending_unresolved'], ['eth7'])
        self.assertEqual(status['reclaimed'], {})

    def test_second_pending_node_makes_reclaim_ambiguous(self):
        # two pending nodes (eth1 and eth7), but only one candidate showed
        # up this boot - which one it belongs to can't be told, so
        # neither is matched; the candidate still gets a real,
        # settings-free name via ordinary bootstrap naming.
        configured = {'m0': 'eth0'}
        pending = {'ethernet': {'eth1', 'eth7'}, 'wireless': set()}
        state = {'eth0': 'm0', 'eth9': 'aa:bb:cc:dd:ee:07'}

        def fake_discover(*_a, **_kw):
            return dict(state)

        def fake_run(command, *_a, **_kw):
            parts = command.split()
            if 'name' in parts:
                old = parts[parts.index('dev') + 1]
                new = parts[parts.index('name') + 1]
                if old in state:
                    state[new] = state.pop(old)
            return 0

        with mock.patch.object(resolver, 'get_configfile_interfaces',
                                return_value=configured), \
             mock.patch.object(resolver, 'get_pending_hwid_nodes',
                                return_value=pending), \
             mock.patch.object(resolver, 'discover_physical_interfaces',
                                side_effect=fake_discover), \
             mock.patch.object(resolver, 'is_wireless_interface',
                                return_value=False), \
             mock.patch.object(resolver, 'pcie_distance', return_value=0), \
             mock.patch.object(
                 resolver, 'pcie_address',
                 return_value=resolver.PCIE_ADDRESS_UNKNOWN), \
             mock.patch.object(resolver, 'run', side_effect=fake_run), \
             mock.patch('time.sleep'):
            resolver.main()

        self.assertNotIn('eth1', state)
        self.assertNotIn('eth7', state)
        self.assertEqual(state.get('eth2'), 'aa:bb:cc:dd:ee:07')

        status = json.loads(resolver.status_file.read_text())
        self.assertEqual(status['pending_unresolved'], ['eth1', 'eth7'])
        self.assertEqual(status['reclaimed'], {})

    def test_ambiguous_candidates_never_get_a_permanent_wrong_binding(self):
        # field report: deleting eth2's hw-id (leaving its node in place)
        # produced "0 unconfigured candidates" on a later boot, because an
        # EARLIER ambiguous boot had already permanently bound the wrong
        # candidate elsewhere. One pending node with two candidates this
        # boot must not be guessed at either way - it stays pending, and
        # both candidates still get a real, settings-free hw-id via
        # ordinary bootstrap naming (the one open gap, then a fresh slot).
        configured = {'m0': 'eth0'}
        pending = {'ethernet': {'eth2'}, 'wireless': set()}
        state = {
            'eth0': 'm0',
            'racyA': 'aa:bb:cc:dd:ee:02',  # eth2's own hardware
            'racyB': 'ff:ff:ff:ff:ff:99',  # unrelated leftover candidate
        }

        def fake_discover(*_a, **_kw):
            return dict(state)

        def fake_run(command, *_a, **_kw):
            parts = command.split()
            if 'name' in parts:
                old = parts[parts.index('dev') + 1]
                new = parts[parts.index('name') + 1]
                if old in state:
                    state[new] = state.pop(old)
            return 0

        with mock.patch.object(resolver, 'get_configfile_interfaces',
                                return_value=configured), \
             mock.patch.object(resolver, 'get_pending_hwid_nodes',
                                return_value=pending), \
             mock.patch.object(resolver, 'discover_physical_interfaces',
                                side_effect=fake_discover), \
             mock.patch.object(resolver, 'is_wireless_interface',
                                return_value=False), \
             mock.patch.object(resolver, 'pcie_distance', return_value=0), \
             mock.patch.object(
                 resolver, 'pcie_address',
                 return_value=resolver.PCIE_ADDRESS_UNKNOWN), \
             mock.patch.object(resolver, 'run', side_effect=fake_run), \
             mock.patch('time.sleep'):
            resolver.main()

        # 'eth2' stays pending; both candidates land on real, settings-
        # free names instead (the one open gap, then a fresh slot)
        self.assertNotIn('eth2', state)
        self.assertEqual(state.get('eth1'), 'aa:bb:cc:dd:ee:02')
        self.assertEqual(state.get('eth3'), 'ff:ff:ff:ff:ff:99')

        hints = set(os.listdir(self.udev_dir))
        self.assertEqual(hints, {'eth1', 'eth3'})

        status = json.loads(resolver.status_file.read_text())
        self.assertEqual(status['pending_unresolved'], ['eth2'])
        self.assertEqual(status['reclaimed'], {})

    def test_simultaneous_pending_nodes_are_covered_by_their_hardware(self):
        # two NICs' hw-id were deleted before the same reboot (eth0 and
        # eth2, nodes left in place), and both came back racily named.
        # This is an exact cover - 2 pending nodes, 2 unconfigured
        # candidates - so both nodes are filled, paired in canonical
        # hardware order. Holding them back instead (the earlier policy)
        # left eth0/eth2's addresses configured on interfaces that never
        # came to exist, permanently, while the hardware bootstrapped at
        # eth8/eth9; every node gets real hardware either way here, so
        # only the permutation is open and PCI slot order decides it.
        # The pairing is logged as a warning for exactly that reason.
        configured = {
            'm1': 'eth1', 'm3': 'eth3', 'm4': 'eth4',
            'm5': 'eth5', 'm6': 'eth6', 'm7': 'eth7',
        }
        pending = {'ethernet': {'eth0', 'eth2'}, 'wireless': set()}
        state = {name: mac for mac, name in configured.items()}
        state.update({
            'racyA': 'aa:bb:cc:dd:ee:00',  # looks like eth0's old hardware
            'racyB': 'aa:bb:cc:dd:ee:02',  # looks like eth2's old hardware
        })

        def fake_discover(*_a, **_kw):
            return dict(state)

        def fake_run(command, *_a, **_kw):
            parts = command.split()
            if 'name' in parts:
                old = parts[parts.index('dev') + 1]
                new = parts[parts.index('name') + 1]
                if old in state:
                    state[new] = state.pop(old)
            return 0

        with mock.patch.object(resolver, 'get_configfile_interfaces',
                                return_value=configured), \
             mock.patch.object(resolver, 'get_pending_hwid_nodes',
                                return_value=pending), \
             mock.patch.object(resolver, 'discover_physical_interfaces',
                                side_effect=fake_discover), \
             mock.patch.object(resolver, 'is_wireless_interface',
                                return_value=False), \
             mock.patch.object(resolver, 'pcie_distance', return_value=0), \
             mock.patch.object(
                 resolver, 'pcie_address',
                 return_value=resolver.PCIE_ADDRESS_UNKNOWN), \
             mock.patch.object(resolver, 'run', side_effect=fake_run), \
             mock.patch('time.sleep'):
            resolver.main()

        # both pending nodes now have real hardware under them, and
        # nothing was bootstrapped past the highest configured index
        self.assertEqual(state.get('eth0'), 'aa:bb:cc:dd:ee:00')
        self.assertEqual(state.get('eth2'), 'aa:bb:cc:dd:ee:02')
        self.assertNotIn('eth8', state)
        self.assertNotIn('eth9', state)

        # hints under the reclaimed names, so vyos-interface-rescan.py
        # writes the fresh hw-id into the EXISTING node and its address
        # and description survive
        hints = set(os.listdir(self.udev_dir))
        self.assertEqual(hints, {'eth0', 'eth2'})

        status = json.loads(resolver.status_file.read_text())
        self.assertEqual(status['pending_unresolved'], [])
        self.assertEqual(status['reclaimed'], {'aa:bb:cc:dd:ee:00': 'eth0',
                                                'aa:bb:cc:dd:ee:02': 'eth2'})
        # inferred from slot order rather than being the single
        # possibility - surfaced separately so an admin can verify it
        self.assertEqual(status['reclaimed_by_topology'], ['eth0', 'eth2'])

    def test_cloud_init_multi_nic_addresses_are_not_stranded(self):
        """Field report, kvm/libvirt qcow2 + NoCloud user-data on a three
        NIC guest: cloud-init synthesized an hw-id for eth0 only, while
        `vyos_config_commands` also set addresses on eth1 and eth2. That
        left 2 pending nodes and 2 unconfigured NICs, which used to be
        refused as ambiguous while eth1/eth2 stayed RESERVED (eth0's
        hw-id makes has_established_baseline() true) - so the real NICs
        were renamed to eth3/eth4 and both configured addresses sat on
        interfaces that did not exist, across reboots.
        """
        configured = {'52:54:00:00:00:10': 'eth0'}
        pending = {'ethernet': {'eth1', 'eth2'}, 'wireless': set()}
        state = {
            'eth0': '52:54:00:00:00:10',
            'eth1': '52:54:00:ff:00:21',  # libvirt slot 0000:00:05.0
            'eth2': '52:54:00:00:00:22',  # libvirt slot 0000:00:06.0
        }
        slots = {
            'eth0': ((0, 0, 4, 0),),
            'eth1': ((0, 0, 5, 0),),
            'eth2': ((0, 0, 6, 0),),
        }

        def fake_discover(*_a, **_kw):
            return dict(state)

        def fake_run(command, *_a, **_kw):
            parts = command.split()
            if 'name' in parts:
                old = parts[parts.index('dev') + 1]
                new = parts[parts.index('name') + 1]
                if old in state:
                    state[new] = state.pop(old)
                    slots[new] = slots.pop(old, resolver.PCIE_ADDRESS_UNKNOWN)
            return 0

        with mock.patch.object(resolver, 'get_configfile_interfaces',
                                return_value=configured), \
             mock.patch.object(resolver, 'get_pending_hwid_nodes',
                                return_value=pending), \
             mock.patch.object(resolver, 'discover_physical_interfaces',
                                side_effect=fake_discover), \
             mock.patch.object(resolver, 'is_wireless_interface',
                                return_value=False), \
             mock.patch.object(resolver, 'pcie_distance', return_value=1), \
             mock.patch.object(
                 resolver, 'pcie_address',
                 side_effect=lambda name: slots.get(
                     name, resolver.PCIE_ADDRESS_UNKNOWN)), \
             mock.patch.object(resolver, 'run', side_effect=fake_run), \
             mock.patch('time.sleep'):
            resolver.main()

        # nothing moved, and in particular nothing landed on eth3/eth4
        self.assertEqual(state, {
            'eth0': '52:54:00:00:00:10',
            'eth1': '52:54:00:ff:00:21',
            'eth2': '52:54:00:00:00:22',
        })

        # hints under eth1/eth2 so vyos-interface-rescan.py writes the
        # hw-id into those EXISTING nodes and their addresses survive.
        # eth0 already has an hw-id, so it needs no hint.
        self.assertEqual(set(os.listdir(self.udev_dir)), {'eth1', 'eth2'})

        status = json.loads(resolver.status_file.read_text())
        self.assertEqual(status['pending_unresolved'], [])
        self.assertEqual(status['renamed'], {})
        self.assertEqual(status['reclaimed'], {'52:54:00:ff:00:21': 'eth1',
                                                '52:54:00:00:00:22': 'eth2'})

    def test_cloud_init_multi_nic_names_follow_pci_slot_order(self):
        """Second field report, same shape: the addresses matched their
        logical names, but the resolver swapped WHICH physical NIC each
        name identified. Both NICs sit at the same PCIe depth, so the old
        (distance, mac) key fell through to raw MAC magnitude - and
        52:54:00:00:00:22 (slot 6) sorts below 52:54:00:ff:00:21 (slot 5),
        reversing the hypervisor's attach order. Both data links then had
        100% packet loss, silently, and the swap froze into config.boot.
        Here the NICs arrive under the OPPOSITE names to make the point.
        """
        configured = {}
        pending = {'ethernet': {'eth1', 'eth2'}, 'wireless': set()}
        state = {
            'eth1': '52:54:00:00:00:22',  # slot 6, arrived first this boot
            'eth2': '52:54:00:ff:00:21',  # slot 5
        }
        slots = {
            'eth1': ((0, 0, 6, 0),),
            'eth2': ((0, 0, 5, 0),),
        }

        def fake_discover(*_a, **_kw):
            return dict(state)

        def fake_run(command, *_a, **_kw):
            parts = command.split()
            if 'name' in parts:
                old = parts[parts.index('dev') + 1]
                new = parts[parts.index('name') + 1]
                if old in state:
                    state[new] = state.pop(old)
                    slots[new] = slots.pop(old, resolver.PCIE_ADDRESS_UNKNOWN)
            return 0

        with mock.patch.object(resolver, 'get_configfile_interfaces',
                                return_value=configured), \
             mock.patch.object(resolver, 'get_pending_hwid_nodes',
                                return_value=pending), \
             mock.patch.object(resolver, 'discover_physical_interfaces',
                                side_effect=fake_discover), \
             mock.patch.object(resolver, 'is_wireless_interface',
                                return_value=False), \
             mock.patch.object(resolver, 'pcie_distance', return_value=1), \
             mock.patch.object(
                 resolver, 'pcie_address',
                 side_effect=lambda name: slots.get(
                     name, resolver.PCIE_ADDRESS_UNKNOWN)), \
             mock.patch.object(resolver, 'run', side_effect=fake_run), \
             mock.patch('time.sleep'):
            resolver.main()

        # the lower PCI slot takes the lower name, whatever the MACs say
        self.assertEqual(state['eth1'], '52:54:00:ff:00:21')
        self.assertEqual(state['eth2'], '52:54:00:00:00:22')

        status = json.loads(resolver.status_file.read_text())
        self.assertEqual(status['pending_unresolved'], [])
        self.assertEqual(status['reclaimed'], {'52:54:00:ff:00:21': 'eth1',
                                                '52:54:00:00:00:22': 'eth2'})

    def test_squatting_pending_candidate_still_reclaims_correctly(self):
        # field report: deleting eth7's hw-id (node left in place) produced
        # a "0 unconfigured candidates" boot even though eth7's real
        # hardware was present, and it later turned up permanently bound
        # to a fresh eth8/eth9-style name. Root cause: eth7's hardware
        # (mac07) happened to be squatting on eth2's configured hw-id slot
        # this boot (probe-order scrambling) - compute_rename_plan()
        # already scheduled it for eviction, which used to make
        # unmatched_candidates() skip it entirely, so it never reached the
        # ascending fill and fell through to a stale, unrelated fallback
        # destination instead. A squatting candidate must still reclaim
        # its pending node exactly like a non-squatting one would, when it
        # is the only open name and the only candidate this boot.
        configured = {
            'm0': 'eth0', 'm1': 'eth1', 'm2': 'eth2', 'm3': 'eth3',
            'm4': 'eth4', 'm5': 'eth5', 'm6': 'eth6',
        }
        pending = {'ethernet': {'eth7'}, 'wireless': set()}
        state = {name: mac for mac, name in configured.items()}
        state.update({
            'eth2': 'aa:bb:cc:dd:ee:07',  # eth7's hardware squats on eth2
            'eth9': 'm2',                 # m2's rightful NIC, racy this boot
        })

        def fake_discover(*_a, **_kw):
            return dict(state)

        def fake_run(command, *_a, **_kw):
            parts = command.split()
            if 'name' in parts:
                old = parts[parts.index('dev') + 1]
                new = parts[parts.index('name') + 1]
                if old in state:
                    state[new] = state.pop(old)
            return 0

        with mock.patch.object(resolver, 'get_configfile_interfaces',
                                return_value=configured), \
             mock.patch.object(resolver, 'get_pending_hwid_nodes',
                                return_value=pending), \
             mock.patch.object(resolver, 'discover_physical_interfaces',
                                side_effect=fake_discover), \
             mock.patch.object(resolver, 'is_wireless_interface',
                                return_value=False), \
             mock.patch.object(resolver, 'pcie_distance', return_value=0), \
             mock.patch.object(
                 resolver, 'pcie_address',
                 return_value=resolver.PCIE_ADDRESS_UNKNOWN), \
             mock.patch.object(resolver, 'run', side_effect=fake_run), \
             mock.patch('time.sleep'):
            resolver.main()

        # m2 still lands on its own configured slot, and the squatter
        # reclaims 'eth7' - not some unrelated fresh bootstrap slot
        self.assertEqual(state.get('eth2'), 'm2')
        self.assertEqual(state.get('eth7'), 'aa:bb:cc:dd:ee:07')
        self.assertNotIn('eth8', state)
        self.assertNotIn('eth9', state)

        hints = set(os.listdir(self.udev_dir))
        self.assertEqual(hints, {'eth7'})

        status = json.loads(resolver.status_file.read_text())
        self.assertEqual(status['reclaimed'], {'aa:bb:cc:dd:ee:07': 'eth7'})
        self.assertEqual(status['pending_unresolved'], [])

    def test_squatting_candidate_and_extra_candidate_makes_reclaim_ambiguous(self):
        # same squatter-eviction shape as the test above, but with a
        # second, unrelated candidate also present this boot - genuinely
        # ambiguous, exactly like a non-squatting extra candidate would
        # be. The pending node stays unresolved; the squatter still gets
        # evicted off of the configured slot it's sitting on (so the
        # rightful owner isn't blocked) and, like the stray, lands on a
        # real, settings-free bootstrap name instead of the pending one.
        configured = {
            'm0': 'eth0', 'm1': 'eth1', 'm2': 'eth2',
            'm3': 'eth3', 'm4': 'eth4', 'm5': 'eth5',
        }
        pending = {'ethernet': {'eth7'}, 'wireless': set()}
        state = {name: mac for mac, name in configured.items()}
        state.update({
            'eth3': 'aa:bb:cc:dd:ee:07',   # squats on m3's configured slot
            'eth9': 'm3',                  # m3's rightful NIC, racy this boot
            'racyC': 'ff:ff:ff:ff:ff:99',  # unrelated leftover candidate
        })

        def fake_discover(*_a, **_kw):
            return dict(state)

        def fake_run(command, *_a, **_kw):
            parts = command.split()
            if 'name' in parts:
                old = parts[parts.index('dev') + 1]
                new = parts[parts.index('name') + 1]
                if old in state:
                    state[new] = state.pop(old)
            return 0

        with mock.patch.object(resolver, 'get_configfile_interfaces',
                                return_value=configured), \
             mock.patch.object(resolver, 'get_pending_hwid_nodes',
                                return_value=pending), \
             mock.patch.object(resolver, 'discover_physical_interfaces',
                                side_effect=fake_discover), \
             mock.patch.object(resolver, 'is_wireless_interface',
                                return_value=False), \
             mock.patch.object(resolver, 'pcie_distance', return_value=0), \
             mock.patch.object(
                 resolver, 'pcie_address',
                 return_value=resolver.PCIE_ADDRESS_UNKNOWN), \
             mock.patch.object(resolver, 'run', side_effect=fake_run), \
             mock.patch('time.sleep'):
            resolver.main()

        # m3 still lands on its own configured slot; 'eth7' stays pending
        # rather than being guessed at; the squatter and the stray both
        # land on real, settings-free names instead
        self.assertEqual(state.get('eth3'), 'm3')
        self.assertNotIn('eth7', state)
        self.assertEqual(state.get('eth6'), 'aa:bb:cc:dd:ee:07')
        self.assertEqual(state.get('eth8'), 'ff:ff:ff:ff:ff:99')

        hints = set(os.listdir(self.udev_dir))
        self.assertEqual(hints, {'eth6', 'eth8'})

        status = json.loads(resolver.status_file.read_text())
        self.assertEqual(status['pending_unresolved'], ['eth7'])
        self.assertEqual(status['reclaimed'], {})

    def test_gap_backfill_and_pending_node_coexisting_stays_ambiguous(self):
        # the exact vyos-build check-qemu-install --ifnametest shape: one
        # interface's whole config node is fully deleted (a free numeric
        # gap) while a DIFFERENT interface's hw-id alone is deleted (a
        # pending node) in the very same reboot
        # (del_idx, hwid_idx = random.sample(range(8), 2)). This is
        # genuinely ambiguous for the pending node (eth2): its own
        # hardware and the gap's freed hardware are two indistinguishable
        # candidates of the same type, and guessing risks silently
        # binding eth2's settings to the wrong physical NIC - confirmed
        # in the field. eth2 stays pending; both candidates still get a
        # real, settings-free hw-id via ordinary bootstrap naming (the
        # actual gap, then a fresh slot) - nothing is lost, just not
        # auto-attributed to the right name.
        configured = {
            'm0': 'eth0', 'm1': 'eth1', 'm3': 'eth3', 'm4': 'eth4',
            'm6': 'eth6', 'm8': 'eth8', 'm9': 'eth9',
        }
        pending = {'ethernet': {'eth2'}, 'wireless': set()}
        state = {name: mac for mac, name in configured.items()}
        state.update({
            'eth7': 'aa:bb:cc:dd:ee:02',  # eth2's real hardware, racy this boot
            'eth5': 'ff:ff:ff:ff:ff:05',  # eth5 fully deleted, its own hardware freed
        })

        def fake_discover(*_a, **_kw):
            return dict(state)

        def fake_run(command, *_a, **_kw):
            parts = command.split()
            if 'name' in parts:
                old = parts[parts.index('dev') + 1]
                new = parts[parts.index('name') + 1]
                if old in state:
                    state[new] = state.pop(old)
            return 0

        with mock.patch.object(resolver, 'get_configfile_interfaces',
                                return_value=configured), \
             mock.patch.object(resolver, 'get_pending_hwid_nodes',
                                return_value=pending), \
             mock.patch.object(resolver, 'discover_physical_interfaces',
                                side_effect=fake_discover), \
             mock.patch.object(resolver, 'is_wireless_interface',
                                return_value=False), \
             mock.patch.object(resolver, 'pcie_distance', return_value=0), \
             mock.patch.object(
                 resolver, 'pcie_address',
                 return_value=resolver.PCIE_ADDRESS_UNKNOWN), \
             mock.patch.object(resolver, 'run', side_effect=fake_run), \
             mock.patch('time.sleep'):
            resolver.main()

        self.assertNotIn('eth2', state)
        self.assertEqual(state.get('eth5'), 'aa:bb:cc:dd:ee:02')
        self.assertEqual(state.get('eth7'), 'ff:ff:ff:ff:ff:05')

        status = json.loads(resolver.status_file.read_text())
        self.assertEqual(status['pending_unresolved'], ['eth2'])
        self.assertEqual(status['reclaimed'], {})


class TestWriteStatus(unittest.TestCase):
    """A pending node that couldn't be safely auto-matched must be
    reported so vyos-router can surface a boot-time warning - it must
    never regress into another silent, buried-syslog-only failure like
    the one this whole fix closes.
    """

    def setUp(self):
        status_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, status_dir, ignore_errors=True)
        self._orig_status_file = resolver.status_file
        resolver.status_file = resolver.Path(status_dir) / 'status.json'
        self.addCleanup(setattr, resolver, 'status_file', self._orig_status_file)

    def _read_status(self):
        return json.loads(resolver.status_file.read_text())

    def test_pending_unresolved_reported_when_no_match(self):
        pending = {'ethernet': {'eth1', 'eth4'}, 'wireless': set()}
        resolver.write_status({}, {}, set(), {}, pending=pending, reclaimed={})
        status = self._read_status()
        self.assertEqual(status['pending_unresolved'], ['eth1', 'eth4'])

    def test_reclaimed_not_reported_as_unresolved(self):
        pending = {'ethernet': {'eth1'}, 'wireless': set()}
        reclaimed = {'m1': 'eth1'}
        resolver.write_status({}, {}, set(), {}, pending=pending,
                               reclaimed=reclaimed)
        status = self._read_status()
        self.assertEqual(status['pending_unresolved'], [])
        self.assertEqual(status['reclaimed'], {'m1': 'eth1'})

    def test_no_pending_no_crash(self):
        resolver.write_status({}, {}, set(), {})
        status = self._read_status()
        self.assertEqual(status['pending_unresolved'], [])
        self.assertEqual(status['reclaimed'], {})

    def test_unconfigured_candidates_reported_for_diagnosis(self):
        # the full unmatched_candidates() list from main(), so an
        # ambiguous reclaim (zero or multiple candidates for a pending
        # node) is diagnosable from this one file alone - which physical
        # interfaces were actually competing - without needing a separate
        # `ip -br link show` or `show configuration commands` to
        # reconstruct the same picture by hand.
        pending = {'ethernet': {'eth7'}, 'wireless': set()}
        candidates = [('aa:bb:cc:dd:ee:07', 'eth9'), ('aa:bb:cc:dd:ee:99', 'vyeth13')]
        resolver.write_status({}, {}, set(), {}, pending=pending,
                               reclaimed={}, candidates=candidates)
        status = self._read_status()
        self.assertEqual(status['pending_unresolved'], ['eth7'])
        self.assertEqual(status['unconfigured_candidates'], {
            'eth9': 'aa:bb:cc:dd:ee:07',
            'vyeth13': 'aa:bb:cc:dd:ee:99',
        })

    def test_unconfigured_candidates_defaults_empty(self):
        resolver.write_status({}, {}, set(), {})
        status = self._read_status()
        self.assertEqual(status['unconfigured_candidates'], {})


class TestBootOrdering(unittest.TestCase):
    """Regression guard for the config.boot availability corner case:
    /opt/vyatta/etc/config/config.boot does not exist until vyos-router
    mounts (and, for an encrypted config volume, decrypts) the config
    directory itself. vyos-net-name-resolve must be started explicitly
    from inside vyos-router after that point, and must not be
    reintroduced as an independently-scheduled unit ordered before
    vyos-router/network-pre.target/cloud-init.
    """

    def setUp(self):
        path = os.path.join(_here, '../init/vyos-router')
        with open(path) as f:
            self.lines = f.readlines()

    def _first_index(self, needle):
        for i, line in enumerate(self.lines):
            if needle in line:
                return i
        self.fail(f"'{needle}' not found in src/init/vyos-router")

    def test_resolver_runs_after_migrate_and_before_config_apply(self):
        # search for call SITES, not the function definitions further up
        migrate = self._first_index('migrate_bootfile || overall_status=1')
        resolve = self._first_index(
            'systemctl start vyos-net-name-resolve.service')
        update_iface = self._first_index('update_interface_config || overall_status=1')
        load_boot = self._first_index('disabled configure || load_bootfile')

        self.assertLess(migrate, resolve,
            'resolver must run after config.boot is migrated/current')
        self.assertLess(resolve, update_iface,
            'resolver must run before new-hardware rescan consumes its hints')
        self.assertLess(resolve, load_boot,
            'resolver must run before the CLI config is applied')

    def test_service_unit_not_independently_ordered_before_vyos_router(self):
        path = os.path.join(_here, '../systemd/vyos-net-name-resolve.service')
        with open(path) as f:
            unit = f.read()
        self.assertNotIn('Before=vyos-router.service', unit)
        self.assertNotIn('Before=network-pre.target', unit)
        self.assertNotIn('WantedBy=', unit)


if __name__ == '__main__':
    unittest.main()
