# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

import importlib.machinery
import importlib.util
from unittest import TestCase

from vyos.configtree import ConfigTree

migration_script = 'src/migration-scripts/ospf/2-to-3'

ospf = ['protocols', 'ospf']
vrf_ospf = ['vrf', 'name', 'red', 'protocols', 'ospf']


def load_migrate():
    loader = importlib.machinery.SourceFileLoader('ospf_2_to_3', migration_script)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module.migrate


def opaque_lsa(base):
    return base + ['parameters', 'opaque-lsa']


def capability_opaque(base):
    return base + ['capability', 'opaque']


class TestOspfOpaqueLsaMigration(TestCase):
    def setUp(self):
        self.migrate = load_migrate()

    def test_no_ospf(self):
        # must not raise when OSPF is not configured
        config = ConfigTree('system {\n    host-name vyos\n}\n')
        self.migrate(config)
        self.assertFalse(config.exists(ospf))
        self.assertFalse(config.exists(['vrf']))

    def test_neither_node(self):
        config = ConfigTree(
            'protocols {\n'
            '    ospf {\n'
            '        parameters {\n'
            '            router-id 192.0.2.1\n'
            '        }\n'
            '    }\n'
            '}\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(capability_opaque(ospf)))
        self.assertEqual(
            config.return_value(ospf + ['parameters', 'router-id']), '192.0.2.1'
        )

    def test_global_instance(self):
        config = ConfigTree(
            'protocols {\n'
            '    ospf {\n'
            '        parameters {\n'
            '            opaque-lsa\n'
            '            router-id 192.0.2.1\n'
            '        }\n'
            '    }\n'
            '}\n'
        )
        self.migrate(config)
        self.assertTrue(config.exists(capability_opaque(ospf)))
        self.assertFalse(config.exists(opaque_lsa(ospf)))
        # the other parameters stay
        self.assertEqual(
            config.return_value(ospf + ['parameters', 'router-id']), '192.0.2.1'
        )

    def test_empty_parameters_node_is_removed(self):
        config = ConfigTree(
            'protocols {\n'
            '    ospf {\n'
            '        parameters {\n'
            '            opaque-lsa\n'
            '        }\n'
            '    }\n'
            '}\n'
        )
        self.migrate(config)
        self.assertTrue(config.exists(capability_opaque(ospf)))
        self.assertFalse(config.exists(ospf + ['parameters']))

    def test_vrf_instance(self):
        # FRR refuses opaque LSAs outside the default VRF: the option never
        # took effect there, so it is dropped, not turned into "capability
        # opaque" (which FRR would refuse at commit time)
        config = ConfigTree(
            'vrf {\n'
            '    name red {\n'
            '        protocols {\n'
            '            ospf {\n'
            '                parameters {\n'
            '                    opaque-lsa\n'
            '                    router-id 192.0.2.2\n'
            '                }\n'
            '            }\n'
            '        }\n'
            '        table 1000\n'
            '    }\n'
            '}\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(capability_opaque(vrf_ospf)))
        self.assertFalse(config.exists(opaque_lsa(vrf_ospf)))
        self.assertEqual(
            config.return_value(vrf_ospf + ['parameters', 'router-id']), '192.0.2.2'
        )
        # nothing is created in the default VRF
        self.assertFalse(config.exists(ospf))

    def test_vrf_capability_opaque_dropped(self):
        # a VRF instance that already has "capability opaque" set directly
        # (without "parameters opaque-lsa") is just as refused by FRR; drop it
        config = ConfigTree(
            'vrf {\n'
            '    name red {\n'
            '        protocols {\n'
            '            ospf {\n'
            '                capability {\n'
            '                    opaque\n'
            '                }\n'
            '                parameters {\n'
            '                    router-id 192.0.2.2\n'
            '                }\n'
            '            }\n'
            '        }\n'
            '        table 1000\n'
            '    }\n'
            '}\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(capability_opaque(vrf_ospf)))
        self.assertFalse(config.exists(vrf_ospf + ['capability']))
        self.assertEqual(
            config.return_value(vrf_ospf + ['parameters', 'router-id']), '192.0.2.2'
        )

    def test_both_nodes_set_in_vrf(self):
        # both the dead "parameters opaque-lsa" deletion and the "capability
        # opaque" drop fire for the same VRF instance in one pass
        config = ConfigTree(
            'vrf {\n'
            '    name red {\n'
            '        protocols {\n'
            '            ospf {\n'
            '                capability {\n'
            '                    opaque\n'
            '                }\n'
            '                parameters {\n'
            '                    opaque-lsa\n'
            '                }\n'
            '            }\n'
            '        }\n'
            '        table 1000\n'
            '    }\n'
            '}\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(capability_opaque(vrf_ospf)))
        self.assertFalse(config.exists(opaque_lsa(vrf_ospf)))
        self.assertFalse(config.exists(vrf_ospf + ['capability']))
        self.assertFalse(config.exists(vrf_ospf + ['parameters']))

    def test_global_and_vrf_instances_are_independent(self):
        # the default instance keeps the move to "capability opaque"; VRF
        # "red" only loses the dead option; VRF "blue" has neither and must
        # stay as it is
        config = ConfigTree(
            'protocols {\n'
            '    ospf {\n'
            '        parameters {\n'
            '            opaque-lsa\n'
            '        }\n'
            '    }\n'
            '}\n'
            'vrf {\n'
            '    name blue {\n'
            '        protocols {\n'
            '            ospf {\n'
            '                parameters {\n'
            '                    router-id 192.0.2.3\n'
            '                }\n'
            '            }\n'
            '        }\n'
            '    }\n'
            '    name red {\n'
            '        protocols {\n'
            '            ospf {\n'
            '                parameters {\n'
            '                    opaque-lsa\n'
            '                }\n'
            '            }\n'
            '        }\n'
            '    }\n'
            '}\n'
        )
        self.migrate(config)
        blue = ['vrf', 'name', 'blue', 'protocols', 'ospf']
        # capability opaque exists only in the default instance
        self.assertTrue(config.exists(capability_opaque(ospf)))
        self.assertFalse(config.exists(capability_opaque(vrf_ospf)))
        self.assertFalse(config.exists(opaque_lsa(vrf_ospf)))
        self.assertFalse(config.exists(capability_opaque(blue)))
        self.assertEqual(
            config.return_value(blue + ['parameters', 'router-id']), '192.0.2.3'
        )

    def test_both_nodes_set(self):
        config = ConfigTree(
            'protocols {\n'
            '    ospf {\n'
            '        capability {\n'
            '            opaque\n'
            '        }\n'
            '        parameters {\n'
            '            opaque-lsa\n'
            '        }\n'
            '    }\n'
            '}\n'
        )
        self.migrate(config)
        self.assertTrue(config.exists(capability_opaque(ospf)))
        self.assertFalse(config.exists(opaque_lsa(ospf)))

    def test_only_capability_set(self):
        config = ConfigTree(
            'protocols {\n'
            '    ospf {\n'
            '        capability {\n'
            '            opaque\n'
            '        }\n'
            '    }\n'
            '}\n'
        )
        self.migrate(config)
        self.assertTrue(config.exists(capability_opaque(ospf)))
        self.assertFalse(config.exists(ospf + ['parameters']))
