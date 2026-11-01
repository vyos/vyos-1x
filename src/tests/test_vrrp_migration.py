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

migration_script = 'src/migration-scripts/vrrp/4-to-5'

group = ['high-availability', 'vrrp', 'group']
option = 'rfc3768-compatibility'


def load_migrate():
    loader = importlib.machinery.SourceFileLoader('vrrp_4_to_5', migration_script)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module.migrate


def vrrp(groups, disable=False, vpp=('eth0',)):
    """Return a configuration with VRRP groups, a list of
    (name, interface, options)."""
    tmp = 'high-availability {\n'
    if disable:
        tmp += '    disable\n'
    tmp += '    vrrp {\n'
    for name, interface, options in groups:
        tmp += f'        group {name} {{\n'
        tmp += f'            address 192.0.2.10/24\n'
        tmp += f'            interface {interface}\n'
        for opt in options:
            tmp += f'            {opt}\n'
        tmp += '            vrid 10\n'
        tmp += '        }\n'
    tmp += '    }\n}\n'
    if vpp:
        tmp += 'vpp {\n    settings {\n'
        for interface in vpp:
            tmp += f'        interface {interface} {{\n        }}\n'
        tmp += '    }\n}\n'
    return ConfigTree(tmp)


class TestVrrpRfc3768VppMigration(TestCase):
    def setUp(self):
        self.migrate = load_migrate()

    def test_no_vrrp(self):
        # must not raise when VRRP is not configured
        config = ConfigTree('system {\n    host-name vyos\n}\n')
        self.migrate(config)
        self.assertFalse(config.exists(['high-availability']))

    def test_vpp_interface(self):
        config = vrrp([('A', 'eth0', [option])])
        self.migrate(config)
        self.assertFalse(config.exists(group + ['A', option]))
        # the rest of the group stays
        self.assertEqual(config.return_value(group + ['A', 'interface']), 'eth0')
        self.assertEqual(config.return_value(group + ['A', 'vrid']), '10')

    def test_vlan_of_vpp_interface(self):
        config = vrrp([('A', 'eth0.10', [option])])
        self.migrate(config)
        self.assertFalse(config.exists(group + ['A', option]))

    def test_other_interface_stays(self):
        config = vrrp([('A', 'eth1', [option]), ('B', 'eth1.10', [option])])
        self.migrate(config)
        self.assertTrue(config.exists(group + ['A', option]))
        self.assertTrue(config.exists(group + ['B', option]))

    def test_only_the_groups_on_vpp_interfaces(self):
        config = vrrp([('A', 'eth0', [option]), ('B', 'eth1', [option])])
        self.migrate(config)
        self.assertFalse(config.exists(group + ['A', option]))
        self.assertTrue(config.exists(group + ['B', option]))

    def test_group_without_the_option(self):
        config = vrrp([('A', 'eth0', ['preempt-delay 60'])])
        self.migrate(config)
        self.assertEqual(config.return_value(group + ['A', 'preempt-delay']), '60')

    def test_disabled_group_stays(self):
        # the verification ignores a disabled group, so does the migration
        config = vrrp([('A', 'eth0', [option, 'disable'])])
        self.migrate(config)
        self.assertTrue(config.exists(group + ['A', option]))

    def test_high_availability_disabled_stays(self):
        config = vrrp([('A', 'eth0', [option])], disable=True)
        self.migrate(config)
        self.assertTrue(config.exists(group + ['A', option]))

    def test_no_vpp_interface(self):
        config = vrrp([('A', 'eth0', [option])], vpp=())
        self.migrate(config)
        self.assertTrue(config.exists(group + ['A', option]))
