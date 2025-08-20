#!/usr/bin/env python3
#
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

import unittest

from base_vyostest_shim import VyOSUnitTestSHIM
from base_vyostest_shim import CSTORE_GUARD_TIME

from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Section
from vyos.frrender import zebra_daemon
from vyos.utils.process import process_named_running
from vyos.utils.system import sysctl_read

base_path = ['protocols', 'segment-routing']


class TestProtocolsSegmentRouting(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        # call base-classes classmethod
        super(TestProtocolsSegmentRouting, cls).setUpClass()
        # Retrieve FRR daemon PID - it is not allowed to crash, thus PID must remain the same
        cls.daemon_pid = process_named_running(zebra_daemon)
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)
        # Enable CSTORE guard time required by FRR related tests
        cls._commit_guard_time = CSTORE_GUARD_TIME

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        # check process health and continuity
        self.assertEqual(self.daemon_pid, process_named_running(zebra_daemon))

    def test_srv6(self):
        interfaces = Section.interfaces('ethernet', vlan=False)
        locators = {
            'foo1': {'prefix': '2001:a::/64'},
            'foo2': {'prefix': '2001:b::/64', 'usid': {}},
            'foo3': {'prefix': '2001:c::/64', 'format': 'uncompressed-f4024'},
            'foo4': {
                'prefix': '2001:d::/48',
                'block-len': '32',
                'node-len': '16',
                'func-bits': '16',
                'usid': {},
                'format': 'usid-f3216',
            },
        }

        for locator, locator_config in locators.items():
            self.cli_set(
                base_path
                + ['srv6', 'locator', locator, 'prefix', locator_config['prefix']]
            )
            if 'block-len' in locator_config:
                self.cli_set(
                    base_path
                    + [
                        'srv6',
                        'locator',
                        locator,
                        'block-len',
                        locator_config['block-len'],
                    ]
                )
            if 'node-len' in locator_config:
                self.cli_set(
                    base_path
                    + [
                        'srv6',
                        'locator',
                        locator,
                        'node-len',
                        locator_config['node-len'],
                    ]
                )
            if 'func-bits' in locator_config:
                self.cli_set(
                    base_path
                    + [
                        'srv6',
                        'locator',
                        locator,
                        'func-bits',
                        locator_config['func-bits'],
                    ]
                )
            if 'usid' in locator_config:
                self.cli_set(base_path + ['srv6', 'locator', locator, 'behavior-usid'])
            if 'format' in locator_config:
                self.cli_set(
                    base_path
                    + ['srv6', 'locator', locator, 'format', locator_config['format']]
                )

        # verify() - SRv6 should be enabled on at least one interface!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface, 'srv6'])

        self.cli_commit()

        for interface in interfaces:
            self.assertEqual(
                sysctl_read(f'net.ipv6.conf.{interface}.seg6_enabled'), '1'
            )
            self.assertEqual(
                sysctl_read(f'net.ipv6.conf.{interface}.seg6_require_hmac'), '0'
            )  # default

        frrconfig = self.getFRRconfig('segment-routing', endsection='^exit')
        self.assertIn('segment-routing', frrconfig)
        self.assertIn(' srv6', frrconfig)
        self.assertIn('  locators', frrconfig)
        for locator, locator_config in locators.items():
            prefix = locator_config['prefix']
            block_len = locator_config.get('block-len', '40')
            node_len = locator_config.get('node-len', '24')
            func_bits = locator_config.get('func-bits', '16')

            self.assertIn(f'   locator {locator}', frrconfig)
            self.assertIn(
                f'    prefix {prefix} block-len {block_len} node-len {node_len} func-bits {func_bits}',
                frrconfig,
            )

            if 'format' in locator_config:
                self.assertIn(f'    format {locator_config["format"]}', frrconfig)
            if 'usid' in locator_config:
                self.assertIn('    behavior usid', frrconfig)

    def test_srv6_sysctl(self):
        interfaces = Section.interfaces('ethernet', vlan=False)

        # HMAC accept
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface, 'srv6'])
            self.cli_set(base_path + ['interface', interface, 'srv6', 'hmac', 'ignore'])
        self.cli_commit()

        for interface in interfaces:
            self.assertEqual(
                sysctl_read(f'net.ipv6.conf.{interface}.seg6_enabled'), '1'
            )
            self.assertEqual(
                sysctl_read(f'net.ipv6.conf.{interface}.seg6_require_hmac'), '-1'
            )  # ignore

        # HMAC drop
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface, 'srv6'])
            self.cli_set(base_path + ['interface', interface, 'srv6', 'hmac', 'drop'])
        self.cli_commit()

        for interface in interfaces:
            self.assertEqual(
                sysctl_read(f'net.ipv6.conf.{interface}.seg6_enabled'), '1'
            )
            self.assertEqual(
                sysctl_read(f'net.ipv6.conf.{interface}.seg6_require_hmac'), '1'
            )  # drop

        # Disable SRv6 on first interface
        first_if = interfaces[-1]
        self.cli_delete(base_path + ['interface', first_if])
        self.cli_commit()

        self.assertEqual(sysctl_read(f'net.ipv6.conf.{first_if}.seg6_enabled'), '0')


if __name__ == '__main__':
    unittest.main(verbosity=2)
