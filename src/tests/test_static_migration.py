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
import re
from pathlib import Path
from unittest import TestCase

from vyos.configtree import ConfigTree

migration_script = 'src/migration-scripts/quagga/12-to-13'

static = ['protocols', 'static']


def load_migrate():
    loader = importlib.machinery.SourceFileLoader('quagga_12_to_13', migration_script)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module.migrate


def route(body, name='route', prefix='192.0.2.0/24'):
    return (
        'protocols {\n'
        '    static {\n'
        f'        {name} {prefix} {{\n'
        f'{body}'
        '        }\n'
        '    }\n'
        '}\n'
    )


class TestStaticDiscardMigration(TestCase):
    def setUp(self):
        self.migrate = load_migrate()

    def disabled(self, config, node='blackhole', name='route', prefix='192.0.2.0/24'):
        return config.exists(static + [name, prefix, node, 'disable'])

    def test_no_static(self):
        config = ConfigTree('system {\n    host-name vyos\n}\n')
        self.migrate(config)
        self.assertFalse(config.exists(static))

    def test_same_default_distance(self):
        config = ConfigTree(
            route(
                '            blackhole\n'
                '            next-hop 198.51.100.1 {\n'
                '            }\n'
            )
        )
        self.migrate(config)
        self.assertTrue(self.disabled(config))
        self.assertTrue(
            config.exists(
                static + ['route', '192.0.2.0/24', 'next-hop', '198.51.100.1']
            )
        )

    def test_different_distance(self):
        config = ConfigTree(
            route(
                '            blackhole {\n'
                '                distance 250\n'
                '            }\n'
                '            next-hop 198.51.100.1 {\n'
                '            }\n'
            )
        )
        self.migrate(config)
        self.assertFalse(self.disabled(config))

    def test_equal_distance_with_leading_zero(self):
        config = ConfigTree(
            route(
                '            blackhole {\n'
                '                distance 010\n'
                '            }\n'
                '            next-hop 198.51.100.1 {\n'
                '                distance 10\n'
                '            }\n'
            )
        )
        self.migrate(config)
        self.assertTrue(self.disabled(config))

    def test_disabled_next_hop_is_no_conflict(self):
        config = ConfigTree(
            route(
                '            blackhole\n'
                '            next-hop 198.51.100.1 {\n'
                '                disable\n'
                '            }\n'
            )
        )
        self.migrate(config)
        self.assertFalse(self.disabled(config))

    def test_interface_route_reject(self):
        config = ConfigTree(
            route(
                '            reject\n'
                '            interface eth0 {\n'
                '            }\n'
            )
        )
        self.migrate(config)
        self.assertTrue(self.disabled(config, 'reject'))

    def test_dhcp_interface_default_distance(self):
        config = ConfigTree(
            route('            blackhole\n' '            dhcp-interface eth0\n')
        )
        self.migrate(config)
        self.assertTrue(self.disabled(config))

    def test_dhcp_interface_other_distance(self):
        config = ConfigTree(
            route(
                '            blackhole {\n'
                '                distance 250\n'
                '            }\n'
                '            dhcp-interface eth0\n'
            )
        )
        self.migrate(config)
        self.assertFalse(self.disabled(config))

    def test_ipv6(self):
        config = ConfigTree(
            route(
                '            blackhole\n'
                '            next-hop 2001:db8::1 {\n'
                '            }\n',
                name='route6',
                prefix='2001:db8:100::/48',
            )
        )
        self.migrate(config)
        self.assertTrue(
            self.disabled(config, name='route6', prefix='2001:db8:100::/48')
        )

    def test_table(self):
        config = ConfigTree(
            'protocols {\n'
            '    static {\n'
            '        table 100 {\n'
            '            route 192.0.2.0/24 {\n'
            '                blackhole\n'
            '                next-hop 198.51.100.1 {\n'
            '                }\n'
            '            }\n'
            '        }\n'
            '    }\n'
            '}\n'
        )
        self.migrate(config)
        self.assertTrue(
            config.exists(
                static
                + ['table', '100', 'route', '192.0.2.0/24', 'blackhole', 'disable']
            )
        )

    def test_vrf(self):
        config = ConfigTree(
            'vrf {\n'
            '    name red {\n'
            '        protocols {\n'
            '            static {\n'
            '                route 192.0.2.0/24 {\n'
            '                    blackhole\n'
            '                    next-hop 198.51.100.1 {\n'
            '                    }\n'
            '                }\n'
            '            }\n'
            '        }\n'
            '        table 1000\n'
            '    }\n'
            '}\n'
        )
        self.migrate(config)
        self.assertTrue(
            config.exists(
                ['vrf', 'name', 'red']
                + static
                + ['route', '192.0.2.0/24', 'blackhole', 'disable']
            )
        )

    def test_blackhole_and_reject_in_table(self):
        # only the blackhole route used to be rendered, the reject route is
        # the one that gets disabled
        config = ConfigTree(
            'protocols {\n'
            '    static {\n'
            '        table 100 {\n'
            '            route 192.0.2.0/24 {\n'
            '                blackhole {\n'
            '                    distance 250\n'
            '                }\n'
            '                reject\n'
            '            }\n'
            '        }\n'
            '    }\n'
            '}\n'
        )
        self.migrate(config)
        base = static + ['table', '100', 'route', '192.0.2.0/24']
        self.assertTrue(config.exists(base + ['reject', 'disable']))
        self.assertFalse(config.exists(base + ['blackhole', 'disable']))

    def test_blackhole_and_reject_one_disabled(self):
        config = ConfigTree(
            route(
                '            blackhole {\n'
                '                disable\n'
                '            }\n'
                '            reject\n'
            )
        )
        self.migrate(config)
        self.assertTrue(self.disabled(config, 'blackhole'))
        self.assertFalse(self.disabled(config, 'reject'))

    def test_idempotent(self):
        config = ConfigTree(
            route(
                '            blackhole\n'
                '            next-hop 198.51.100.1 {\n'
                '            }\n'
            )
        )
        self.migrate(config)
        self.migrate(config)
        self.assertTrue(self.disabled(config))


class TestQuaggaSyntaxVersion(TestCase):
    def test_declared_version_matches_last_migration(self):
        # the runner only applies 12-to-13 if the component declares version 13
        declared = re.search(
            r"component='quagga' version='(\d+)'",
            Path(
                'interface-definitions/include/version/quagga-version.xml.i'
            ).read_text(),
        )
        last = max(
            int(p.name.split('-to-')[1])
            for p in Path('src/migration-scripts/quagga').glob('*-to-*')
        )
        self.assertEqual(int(declared.group(1)), last)
