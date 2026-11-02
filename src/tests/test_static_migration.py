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

migration_script = 'src/migration-scripts/quagga/12-to-13'

static = ['protocols', 'static']
vrf_static = ['vrf', 'name', 'red', 'protocols', 'static']
default = static + ['route', '0.0.0.0/0']
prefix = static + ['route', '192.0.2.0/24']


def load_migrate():
    loader = importlib.machinery.SourceFileLoader('quagga_12_to_13', migration_script)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module.migrate


class TestStaticDiscardMigration(TestCase):
    def setUp(self):
        self.migrate = load_migrate()
        self.config = ConfigTree('system {\n    host-name vyos\n}\n')

    def set(self, path, value=None):
        self.config.set(path, value=value, replace=False)

    def disabled(self, path):
        return self.config.exists(path + ['disable'])

    def test_no_static(self):
        # must not raise when static routing is not configured
        self.migrate(self.config)
        self.assertFalse(self.config.exists(static))

    def test_next_hop_same_distance(self):
        self.set(prefix + ['blackhole'])
        self.set(prefix + ['next-hop', '198.51.100.1'])
        self.migrate(self.config)
        self.assertTrue(self.disabled(prefix + ['blackhole']))
        self.assertFalse(self.disabled(prefix + ['next-hop', '198.51.100.1']))

    def test_interface_explicit_distance(self):
        # the validator accepts leading zeros
        self.set(prefix + ['reject', 'distance'], '05')
        self.set(prefix + ['interface', 'eth0', 'distance'], '5')
        self.migrate(self.config)
        self.assertTrue(self.disabled(prefix + ['reject']))

    def test_different_distance(self):
        self.set(prefix + ['blackhole', 'distance'], '200')
        self.set(prefix + ['next-hop', '198.51.100.1'])
        self.migrate(self.config)
        self.assertFalse(self.disabled(prefix + ['blackhole']))

    def test_disabled_next_hop(self):
        self.set(prefix + ['blackhole'])
        self.set(prefix + ['next-hop', '198.51.100.1', 'disable'])
        self.migrate(self.config)
        self.assertFalse(self.disabled(prefix + ['blackhole']))

    def test_dhcp_interface(self):
        # rendered without a distance, so only the default distance conflicts
        self.set(prefix + ['blackhole'])
        self.set(prefix + ['dhcp-interface'], 'eth0')
        other = static + ['route', '198.51.100.0/24']
        self.set(other + ['blackhole', 'distance'], '2')
        self.set(other + ['dhcp-interface'], 'eth0')
        self.migrate(self.config)
        self.assertTrue(self.disabled(prefix + ['blackhole']))
        self.assertFalse(self.disabled(other + ['blackhole']))

    def test_blackhole_and_reject(self):
        # only the blackhole route was rendered
        path = static + ['table', '100', 'route', '192.0.2.0/24']
        self.set(path + ['blackhole'])
        self.set(path + ['reject', 'distance'], '250')
        self.migrate(self.config)
        self.assertFalse(self.disabled(path + ['blackhole']))
        self.assertTrue(self.disabled(path + ['reject']))

    def test_blackhole_and_reject_next_to_next_hop(self):
        self.set(prefix + ['blackhole'])
        self.set(prefix + ['reject'])
        self.set(prefix + ['next-hop', '198.51.100.1'])
        self.migrate(self.config)
        self.assertTrue(self.disabled(prefix + ['blackhole']))
        self.assertTrue(self.disabled(prefix + ['reject']))

    def test_vrf_next_hop(self):
        path = vrf_static + ['route6', '2001:db8::/32']
        self.set(['vrf', 'name', 'red', 'table'], '1000')
        self.set(path + ['reject'])
        self.set(path + ['next-hop', '2001:db8::1'])
        self.migrate(self.config)
        self.assertTrue(self.disabled(path + ['reject']))

    def test_interface_default_route_ignored(self):
        # the default route of a PPPoE or DHCP interface is not a static
        # route, FRRender drops a blackhole route next to it
        self.set(['interfaces', 'pppoe', 'pppoe0', 'source-interface'], 'eth0')
        self.set(default + ['blackhole'])
        self.migrate(self.config)
        self.assertFalse(self.disabled(default + ['blackhole']))
