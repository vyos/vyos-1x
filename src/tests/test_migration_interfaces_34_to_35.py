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
# Coverage for the interfaces 34-to-35 migration (T3871): hw-id leaves the
# CLI, and its bindings are carried into the interface mapping store so that
# no interface changes name across the upgrade.

import os
import unittest
from unittest import mock

from helper import prepare_module
from vyos.configtree import ConfigTree
from vyos.ifconfig.ifname_store import STORE_VERSION

_here = os.path.dirname(__file__)

migration = prepare_module(
    os.path.join(_here, '../migration-scripts/interfaces/34-to-35'),
    'interfaces_34_to_35')


def device(name, mac, path):
    properties = {'ID_PATH': path, 'ID_BUS': 'pci'}
    return {'name': name, 'mac': mac, 'wireless': False,
            'properties': properties, 'key': f'ID_PATH={path}'}


CONFIG = """interfaces {
    ethernet eth0 {
        address "192.0.2.1/24"
        hw-id "00:00:5e:00:53:01"
    }
    ethernet eth1 {
        description "uplink"
        hw-id "00:00:5e:00:53:02"
    }
}
"""


class TestMigration34to35(unittest.TestCase):
    def setUp(self):
        self.config = ConfigTree(CONFIG)
        self.saved = []

        patches = [
            mock.patch.object(migration, 'load_store',
                              return_value={'version': STORE_VERSION,
                                            'interfaces': {}}),
            mock.patch.object(migration, 'save_store',
                              side_effect=lambda s: self.saved.append(s) or True),
            mock.patch.object(migration, 'sync_link_files'),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _devices(self, devices):
        return mock.patch.object(migration, 'discover_devices',
                                 return_value=devices)

    def test_hwid_nodes_are_removed(self):
        with self._devices([]):
            migration.migrate(self.config)
        self.assertFalse(self.config.exists(
            ['interfaces', 'ethernet', 'eth0', 'hw-id']))
        self.assertFalse(self.config.exists(
            ['interfaces', 'ethernet', 'eth1', 'hw-id']))

    def test_other_settings_are_untouched(self):
        with self._devices([]):
            migration.migrate(self.config)
        self.assertEqual(
            self.config.return_value(['interfaces', 'ethernet', 'eth0', 'address']),
            '192.0.2.1/24')
        self.assertEqual(
            self.config.return_value(['interfaces', 'ethernet', 'eth1', 'description']),
            'uplink')

    def test_matching_hardware_is_recorded_with_its_slot(self):
        devices = [
            device('eth0', '00:00:5e:00:53:01', 'pci-0000:00:04.0'),
            device('eth1', '00:00:5e:00:53:02', 'pci-0000:00:05.0'),
        ]
        with self._devices(devices):
            migration.migrate(self.config)

        self.assertEqual(len(self.saved), 1)
        entries = self.saved[0]['interfaces']
        self.assertEqual(entries['eth0'], 'ID_PATH=pci-0000:00:04.0')
        self.assertEqual(entries['eth1'], 'ID_PATH=pci-0000:00:05.0')

    def test_names_are_preserved_even_out_of_slot_order(self):
        # a box named by an earlier release in MAC order: eth0 sits in the
        # HIGHER slot. The migration must record what is, not what slot
        # order would suggest, or the upgrade renames its interfaces.
        devices = [
            device('eth0', '00:00:5e:00:53:01', 'pci-0000:00:09.0'),
            device('eth1', '00:00:5e:00:53:02', 'pci-0000:00:03.0'),
        ]
        with self._devices(devices):
            migration.migrate(self.config)
        entries = self.saved[0]['interfaces']
        self.assertEqual(entries['eth0'], 'ID_PATH=pci-0000:00:09.0')
        self.assertEqual(entries['eth1'], 'ID_PATH=pci-0000:00:03.0')

    def test_foreign_config_writes_nothing(self):
        # migrations also run against configuration files from other
        # machines (config tests, a config copied off another box). Nothing
        # matches, so nothing may be written - otherwise this would reserve
        # names for hardware that is not here.
        with self._devices([device('eth0', 'ff:ff:ff:ff:ff:fe', 'pci-0000:00:04.0')]):
            migration.migrate(self.config)
        self.assertEqual(self.saved, [])

    def test_existing_store_entry_is_never_overwritten(self):
        existing = {'version': STORE_VERSION,
                    'interfaces': {'eth0': 'ID_PATH=pci-0000:00:11.0'}}
        devices = [
            device('eth0', '00:00:5e:00:53:01', 'pci-0000:00:04.0'),
            device('eth1', '00:00:5e:00:53:02', 'pci-0000:00:05.0'),
        ]
        with mock.patch.object(migration, 'load_store', return_value=existing), \
             self._devices(devices):
            migration.migrate(self.config)
        entries = self.saved[0]['interfaces']
        self.assertEqual(entries['eth0'], 'ID_PATH=pci-0000:00:11.0')
        self.assertEqual(entries['eth1'], 'ID_PATH=pci-0000:00:05.0')

    def test_slot_already_named_does_not_gain_a_second_name(self):
        # the store already names this slot. Recording the config's name for
        # it too would leave two names on one slot: resolve() gives the slot
        # to the first, so the second reserves a name nothing can ever fill,
        # and sync_link_files() would point two .link files at one device.
        existing = {'version': STORE_VERSION,
                    'interfaces': {'eth0': 'ID_PATH=pci-0000:00:04.0'}}
        config = ConfigTree('interfaces {\n    ethernet eth9 {\n'
                            '        hw-id "00:00:5e:00:53:01"\n    }\n}\n')
        with mock.patch.object(migration, 'load_store', return_value=existing), \
             self._devices([device('eth0', '00:00:5e:00:53:01',
                                    'pci-0000:00:04.0')]):
            migration.migrate(config)

        # nothing new to record, so nothing is written
        self.assertEqual(self.saved, [])
        self.assertNotIn('eth9', existing['interfaces'])

    def test_one_hwid_on_two_nodes_records_only_the_first(self):
        # a malformed config binding the same hw-id twice must not put that
        # slot in the store under both names.
        config = ConfigTree('interfaces {\n'
                            '    ethernet eth0 {\n'
                            '        hw-id "00:00:5e:00:53:01"\n    }\n'
                            '    ethernet eth1 {\n'
                            '        hw-id "00:00:5e:00:53:01"\n    }\n}\n')
        with self._devices([device('eth0', '00:00:5e:00:53:01',
                                    'pci-0000:00:04.0')]):
            migration.migrate(config)

        entries = self.saved[0]['interfaces']
        self.assertEqual(entries, {'eth0': 'ID_PATH=pci-0000:00:04.0'})
        self.assertEqual(len(set(entries.values())), len(entries))

    def test_config_without_hwid_is_a_no_op(self):
        config = ConfigTree('interfaces {\n    ethernet eth0 {\n    }\n}\n')
        with self._devices([device('eth0', '00:00:5e:00:53:01', 'p')]):
            migration.migrate(config)
        self.assertEqual(self.saved, [])


if __name__ == '__main__':
    unittest.main()
