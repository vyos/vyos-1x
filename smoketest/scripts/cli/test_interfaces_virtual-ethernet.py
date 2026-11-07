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

from time import time

from base_interfaces_test import BasicInterfaceTest
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.network import interface_exists
from vyos.utils.network import is_intf_addr_assigned
from vyos.utils.process import rc_cmd

class VEthInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'virtual-ethernet']
        cls._options = {
            'veth0': ['peer-name veth1'],
            'veth1': ['peer-name veth0'],
        }

        cls._interfaces = list(cls._options)
        # call base-classes classmethod
        super(VEthInterfaceTest, cls).setUpClass()

    def test_invalid_peers(self):
        peer = ('veth1001', 'veth1002')
        self.cli_set(self._base_path + [peer[0]])
        self.cli_set(self._base_path + [peer[1], 'peer-name', peer[0]])

        # Configuration mismatch between "veth1001" and "veth1001"
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(self._base_path + [peer[0], 'peer-name', peer[1]])
        self.cli_commit()

        self.assertTrue(interface_exists(peer[0]))
        self.assertTrue(interface_exists(peer[1]))

    def test_dhcpv6_client_unanswered_release(self):
        # T6301: a DHCPv6 server not answering the Release of a stopping
        # client must not block the commit for ~30 seconds
        client, server = 'veth0', 'veth1'
        lease = '2001:db8:6301::100'
        server_path = ['service', 'dhcpv6-server', 'shared-network-name', 'T6301',
                       'subnet', '2001:db8:6301::/64']
        nft_table = 'inet smoketest_t6301'

        for interface in self._interfaces:
            for option in self._options.get(interface, []):
                self.cli_set(self._base_path + [interface] + option.split())
        self.cli_set(self._base_path + [server, 'address', '2001:db8:6301::1/64'])
        self.cli_set(self._base_path + [client, 'address', 'dhcpv6'])
        self.cli_set(server_path + ['subnet-id', '6301'])
        self.cli_set(server_path + ['interface', server])
        self.cli_set(server_path + ['range', '1', 'start', lease])
        self.cli_set(server_path + ['range', '1', 'stop', lease])
        self.cli_commit()

        try:
            self.wait_for_result(lambda: is_intf_addr_assigned(client, lease), True,
                                 timeout=30)
            self.assertTrue(is_intf_addr_assigned(client, lease))

            # Drop the client's Release so it never sees a Reply
            for nft in [f'add table {nft_table}',
                        f"add chain {nft_table} out '{{ type filter hook output priority 0; }}'",
                        f'add rule {nft_table} out oifname {client} udp dport 547 drop']:
                rc, out = rc_cmd(f'sudo nft {nft}')
                self.assertEqual(rc, 0, out)

            self.cli_delete(self._base_path + [client, 'address', 'dhcpv6'])
            start = time()
            self.cli_commit()
            self.assertLess(time() - start, 15)

            self.assertFalse(is_intf_addr_assigned(client, lease))
            # A bounded stop must still be a clean stop
            _, state = rc_cmd(f'systemctl is-failed dhcp6c@{client}.service')
            self.assertEqual(state, 'inactive')
        finally:
            rc_cmd(f'sudo nft delete table {nft_table}')
            self.cli_delete(['service', 'dhcpv6-server'])
            self.cli_commit()

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
