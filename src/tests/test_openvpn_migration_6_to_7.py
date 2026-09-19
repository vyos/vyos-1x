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

migration_script = 'src/migration-scripts/openvpn/6-to-7'

keep_alive = ['interfaces', 'openvpn', 'vtun10', 'keep-alive']


def load_migrate():
    loader = importlib.machinery.SourceFileLoader('openvpn_6_to_7', migration_script)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module.migrate


def config_tree(mode, body=''):
    return ConfigTree(
        'interfaces {\n'
        '    openvpn vtun10 {\n'
        f'        mode {mode}\n'
        f'{body}'
        '    }\n'
        '}\n'
    )


def keepalive(interval, failure_count):
    return (
        '        keep-alive {\n'
        f'            failure-count {failure_count}\n'
        f'            interval {interval}\n'
        '        }\n'
    )


class TestOpenVPNMigration(TestCase):
    def setUp(self):
        self.migrate = load_migrate()

    def test_empty_config(self):
        # must not raise when no OpenVPN interface is configured
        config = ConfigTree('system {\n    host-name vyos\n}\n')
        self.migrate(config)
        self.assertFalse(config.exists(['interfaces', 'openvpn']))

    def test_timeout_within_the_limit_is_kept(self):
        config = config_tree('site-to-site', keepalive(10, 60))
        self.migrate(config)
        self.assertEqual(config.return_value(keep_alive + ['failure-count']), '60')

    def test_timeout_beyond_the_limit_is_clamped(self):
        # 600 * 1000 is far beyond the 24 hours OpenVPN accepts
        config = config_tree('site-to-site', keepalive(600, 1000))
        self.migrate(config)
        # 600 * 144 is exactly 24 hours
        self.assertEqual(config.return_value(keep_alive + ['failure-count']), '144')

    def test_disabled_keepalive_is_left_alone(self):
        config = config_tree('site-to-site', keepalive(0, 1000))
        self.migrate(config)
        self.assertEqual(config.return_value(keep_alive + ['failure-count']), '1000')

    def test_server_mode_is_left_alone(self):
        # the server renders its own "keepalive" and has always multiplied
        config = config_tree('server', keepalive(600, 1000))
        self.migrate(config)
        self.assertEqual(config.return_value(keep_alive + ['failure-count']), '1000')

    def test_defaults_need_no_change(self):
        # both nodes are absent from a saved configuration when left default
        config = config_tree('site-to-site')
        self.migrate(config)
        self.assertFalse(config.exists(keep_alive + ['failure-count']))
