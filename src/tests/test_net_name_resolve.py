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
# Coverage for T3871: the boot-time half of persistent interface naming -
# settling, renaming and boot ordering.
#
# The naming decision and hardware discovery both live in
# vyos.ifconfig.ifname_store and are covered by test_ifname_store.py.

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

_container_patcher = None


def setUpModule():
    # main() deliberately short-circuits inside a container, and these tests
    # are routinely run from one (the VyOS build container). Pin the detection
    # off for the whole module so the naming pass under test actually runs -
    # TestMainInContainer patches it back on locally where that is the point.
    global _container_patcher
    _container_patcher = mock.patch.object(
        resolver, 'is_running_as_container', return_value=False)
    _container_patcher.start()


def tearDownModule():
    _container_patcher.stop()


def device(name, mac, path='', wireless=False):
    return {'name': name, 'mac': mac, 'path': path, 'wireless': wireless,
            'properties': {}}


class TestWaitForSettle(unittest.TestCase):
    """There is no specific MAC to wait for when naming hardware the store
    has never seen, so settling is detected as N consecutive identical
    discover_physical_interfaces() snapshots instead.
    """

    def test_returns_after_n_consecutive_stable_polls(self):
        one = [device('eth0', 'm0')]
        two = [device('eth0', 'm0'), device('eth1', 'm1')]
        snapshots = [one, two, two, two]
        with mock.patch.object(resolver, 'discover_devices',
                               side_effect=snapshots):
            result = resolver.wait_for_settle([], timeout=5, poll=0,
                                              stable_polls=3)
        self.assertEqual(resolver._snapshot(result),
                         {('eth0', 'm0'), ('eth1', 'm1')})

    def test_bounded_by_timeout_when_never_stable(self):
        counter = iter(range(1000))

        def ever_changing(*_a, **_kw):
            return [device('eth0', f'm{next(counter)}')]

        clock = iter([0, 0.1, 20, 20])
        with mock.patch.object(resolver, 'discover_devices',
                               side_effect=ever_changing), \
             mock.patch('time.monotonic', side_effect=lambda: next(clock)):
            result = resolver.wait_for_settle([], timeout=10, poll=0,
                                              stable_polls=3)
        # must return SOMETHING (the last snapshot seen), not hang or crash
        self.assertEqual(len(result), 1)

    def test_stable_polls_of_one_returns_on_initial_snapshot(self):
        initial = [device('eth0', 'm0')]
        with mock.patch.object(resolver, 'discover_devices') as m:
            result = resolver.wait_for_settle(initial, timeout=5, poll=0,
                                              stable_polls=1)
        m.assert_not_called()
        self.assertEqual(result, initial)


class TestSafeBulkRename(unittest.TestCase):
    """Only hardware the store has never seen should reach this on a settled
    system, but when it does the two-phase rename must report accurately: a
    phase-2 (scratch -> final target) failure must not be reported as a
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
        def fake_run(command, *_a, **_kw):
            return 1 if command == 'ip link set dev vyetheth5 name eth0' else 0

        with mock.patch.object(resolver, 'run', side_effect=fake_run):
            applied = resolver.safe_bulk_rename({'eth5': 'eth0'})

        self.assertNotIn('eth5', applied)

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
            applied = resolver.safe_bulk_rename({'eth5': 'eth0',
                                                 'eth9': 'eth1'})

        self.assertNotIn('eth5', applied)
        self.assertEqual(applied.get('eth9'), 'eth1')


class TestMainInContainer(unittest.TestCase):
    """A container owns no NIC: its interfaces are runtime-created veth pairs
    with no backing bus device in sysfs and a host-assigned MAC that changes
    on every start. There is nothing to name and nothing worth persisting.
    """

    def setUp(self):
        status_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, status_dir, ignore_errors=True)
        self._orig_status_file = resolver.status_file
        resolver.status_file = resolver.Path(status_dir) / 'status.json'
        self.addCleanup(setattr, resolver, 'status_file',
                        self._orig_status_file)

    def test_naming_pass_is_skipped_entirely(self):
        with mock.patch.object(resolver, 'is_running_as_container',
                               return_value=True), \
             mock.patch.object(resolver, 'load_store') as load, \
             mock.patch.object(resolver, 'discover_devices') as discover, \
             mock.patch.object(resolver, 'save_store') as save, \
             mock.patch.object(resolver, 'run') as run:
            resolver.main()

        load.assert_not_called()
        discover.assert_not_called()
        save.assert_not_called()
        run.assert_not_called()
        self.assertFalse(resolver.status_file.exists())


class TestBootOrdering(unittest.TestCase):
    """The store lives in the config directory, which does not exist until
    vyos-router mounts (and, for an encrypted config volume, decrypts) it. So
    the pass must be started explicitly from inside vyos-router after that
    point, and must not be reintroduced as an independently-scheduled unit
    ordered before it.
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
        update_iface = self._first_index(
            'update_interface_config || overall_status=1')
        load_boot = self._first_index('disabled configure || load_bootfile')

        self.assertLess(migrate, resolve,
                        'resolver must run after config.boot is current')
        self.assertLess(resolve, update_iface,
                        'resolver must write the store before the rescan reads it')
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
