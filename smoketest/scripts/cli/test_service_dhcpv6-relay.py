#!/usr/bin/env python3
#
# Copyright (C) 2020-2024 VyOS maintainers and contributors
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

from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Section
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file

PROCESS_NAME = 'dhcrelay'
RELAY_CONF = '/run/dhcp-relay/dhcrelay6.conf'
base_path = ['service', 'dhcpv6-relay']

upstream_if = 'eth0'
upstream_if_addr = '2001:db8::1/64'
listen_addr = '2001:db8:ffff::1/64'
interfaces = []

class TestServiceDHCPv6Relay(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestServiceDHCPv6Relay, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

        for tmp in Section.interfaces('ethernet', vlan=False):
            interfaces.append(tmp)
            listen = listen_addr
            if tmp == upstream_if:
                listen = upstream_if_addr
            cls.cli_set(cls, ['interfaces', 'ethernet', tmp, 'address', listen])

    @classmethod
    def tearDownClass(cls):
        for tmp in interfaces:
            listen = listen_addr
            if tmp == upstream_if:
                listen = upstream_if_addr
            cls.cli_delete(cls, ['interfaces', 'ethernet', tmp, 'address', listen])

        super(TestServiceDHCPv6Relay, cls).tearDownClass()

    def test_relay_default(self):
        dhcpv6_server = '2001:db8::ffff'
        hop_count = '20'

        self.cli_set(base_path + ['use-interface-id-option'])
        self.cli_set(base_path + ['max-hop-count', hop_count])

        # check validate() - Must set at least one listen and upstream
        # interface addresses.
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['upstream-interface', upstream_if, 'address', dhcpv6_server])

        # check validate() - Must set at least one listen and upstream
        # interface addresses.
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # add listener on all ethernet interfaces except the upstream interface
        for tmp in interfaces:
            if tmp == upstream_if:
                continue
            self.cli_set(base_path + ['listen-interface', tmp, 'address', listen_addr.split('/')[0]])

        # commit changes
        self.cli_commit()

        # Check configured port
        config = read_file(RELAY_CONF)

        # Test configured upstream interfaces
        self.assertIn(f'-u {dhcpv6_server}%{upstream_if}', config)

        # Check listener on all ethernet interfaces
        for tmp in interfaces:
            if tmp == upstream_if:
                continue
            addr = listen_addr.split('/')[0]
            self.assertIn(f'-l {addr}%{tmp}', config)

        # Check hop count
        self.assertIn(f'-c {hop_count}', config)
        # Check Interface ID option
        self.assertIn('-I', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    unittest.main(verbosity=2)
