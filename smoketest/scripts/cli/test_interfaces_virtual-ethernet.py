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

from time import sleep
from time import time

from base_interfaces_test import BasicInterfaceTest
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.file import read_file
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

    # T9675: DHCP(v6) clients run on a bridge whose only member is veth0, so
    # taking veth0 down drops the carrier of an interface vyos-netlinkd acts on
    # without disabling it. veth1 serves DHCP, DHCPv6 and a delegated prefix,
    # each pool holding exactly one lease.
    _t9675_client = 'br9675'
    _t9675_lan = 'dum9675'
    _t9675_v4 = '192.0.2.100'
    _t9675_v6 = '2001:db8:9675::100'
    _t9675_pd = '2001:db8:96ff::1'

    def _t9675_setup(self):
        client, lan = self._t9675_client, self._t9675_lan
        v4_path = ['service', 'dhcp-server', 'shared-network-name', 'T9675',
                   'subnet', '192.0.2.0/24']
        v6_path = ['service', 'dhcpv6-server', 'shared-network-name', 'T9675',
                   'subnet', '2001:db8:9675::/64']

        for interface in self._interfaces:
            for option in self._options.get(interface, []):
                self.cli_set(self._base_path + [interface] + option.split())
        self.cli_set(self._base_path + ['veth1', 'address', '192.0.2.1/24'])
        self.cli_set(self._base_path + ['veth1', 'address', '2001:db8:9675::1/64'])

        self.cli_set(['service', 'dhcp-server', 'listen-interface', 'veth1'])
        self.cli_set(v4_path + ['subnet-id', '9675'])
        self.cli_set(v4_path + ['range', '0', 'start', self._t9675_v4])
        self.cli_set(v4_path + ['range', '0', 'stop', self._t9675_v4])

        self.cli_set(v6_path + ['subnet-id', '9675'])
        self.cli_set(v6_path + ['interface', 'veth1'])
        self.cli_set(v6_path + ['range', '1', 'start', self._t9675_v6])
        self.cli_set(v6_path + ['range', '1', 'stop', self._t9675_v6])
        pd_path = v6_path + ['prefix-delegation', 'prefix', '2001:db8:96ff::']
        self.cli_set(pd_path + ['delegated-length', '56'])
        self.cli_set(pd_path + ['prefix-length', '56'])

        self.cli_set(['interfaces', 'dummy', lan])
        client_path = ['interfaces', 'bridge', client]
        self.cli_set(client_path + ['member', 'interface', 'veth0'])
        self.cli_set(client_path + ['address', 'dhcp'])
        self.cli_set(client_path + ['address', 'dhcpv6'])
        self.cli_set(client_path + ['dhcpv6-options', 'pd', '0', 'length', '56'])
        self.cli_set(client_path + ['dhcpv6-options', 'pd', '0', 'interface', lan,
                                    'address', '1'])
        self.cli_commit()

    def _t9675_teardown(self):
        rc_cmd('sudo ip link set veth0 up')
        self.cli_delete(['interfaces', 'bridge', self._t9675_client])
        self.cli_delete(['interfaces', 'dummy', self._t9675_lan])
        self.cli_delete(['service', 'dhcp-server'])
        self.cli_delete(['service', 'dhcpv6-server'])
        self.cli_commit()

    def _t9675_leases(self):
        """ (IPv4 lease, IPv6 lease, delegated prefix) present on the router """
        return (is_intf_addr_assigned(self._t9675_client, self._t9675_v4),
                is_intf_addr_assigned(self._t9675_client, self._t9675_v6),
                is_intf_addr_assigned(self._t9675_lan, self._t9675_pd))

    def _t9675_wait_leases(self, expected):
        self.wait_for_result(self._t9675_leases, expected, timeout=30)
        self.assertEqual(self._t9675_leases(), expected)

    @staticmethod
    def _main_pid(unit):
        _, pid = rc_cmd(f'systemctl show --property=MainPID --value {unit}')
        return pid

    @staticmethod
    def _unit_state(unit):
        # A stopping unit is "deactivating" for as long as its Release takes
        _, state = rc_cmd(f'systemctl is-active {unit}')
        return state

    def test_dhcp_clients_carrier_loss(self):
        # T9675: on carrier loss dhclient is stopped while dhcp6c keeps its
        # leases - a Release sent without carrier never reaches the server.
        # Both clients are restarted once the carrier returns.
        client = self._t9675_client
        dhclient, dhcp6c = f'dhclient@{client}.service', f'dhcp6c@{client}.service'

        self._t9675_setup()
        try:
            self._t9675_wait_leases((True, True, True))
            start = int(time())

            # Repeated: lost link events used to shift every later one (T9675)
            for _ in range(3):
                dhcp6c_pid = self._main_pid(dhcp6c)

                rc_cmd('sudo ip link set veth0 down')
                self.wait_for_result(lambda: read_file(f'/sys/class/net/{client}/operstate'),
                                     'down')
                # dhclient being stopped shows the carrier loss was acted on
                self.wait_for_result(lambda: self._unit_state(dhclient), 'inactive')
                self.assertEqual(self._unit_state(dhclient), 'inactive')
                # Give a wrongly stopping dhcp6c the time to go
                sleep(3)
                self.assertEqual(self._unit_state(dhcp6c), 'active')
                self.assertEqual(self._main_pid(dhcp6c), dhcp6c_pid)
                self.assertEqual(self._t9675_leases(), (False, True, True))

                rc_cmd('sudo ip link set veth0 up')
                self._t9675_wait_leases((True, True, True))
                self.assertEqual(self._unit_state(dhclient), 'active')
                self.assertEqual(self._unit_state(dhcp6c), 'active')
                self.assertNotEqual(self._main_pid(dhcp6c), dhcp6c_pid)

            # Each transition must have been acted on from its netlink event,
            # not picked up late by the periodic operstate reconcile
            _, log = rc_cmd(f'sudo journalctl --no-pager --output=cat '
                            f'--identifier=vyos-netlinkd --since=@{start}')
            self.assertNotIn(f'Reconcile {client}:', log)
        finally:
            self._t9675_teardown()

    def test_dhcp_clients_carrier_loss_queued_events(self):
        # T9675: a link event queued behind an IPv6 address event (which has
        # no interface label) was moved into pyroute2's backlog while the name
        # of the address event was resolved, and not acted on until another
        # unrelated netlink event arrived
        client = self._t9675_client
        dhclient = f'dhclient@{client}.service'
        netlinkd_pid = self._main_pid('vyos-netlinkd.service')

        def queued(link_state, address):
            # Finished DAD emits an address event, which would also flush the
            # backlog. Wait for it so nothing but the queued events can.
            self.wait_for_result(lambda: rc_cmd('ip -6 addr show tentative')[1], '')
            # Holding vyos-netlinkd queues both events in the netlink socket
            rc_cmd(f'sudo kill -STOP {netlinkd_pid}')
            try:
                rc_cmd(f'sudo ip -6 addr add {address}/128 dev {self._t9675_lan} nodad')
                rc_cmd(f'sudo ip link set veth0 {link_state}')
                # The bridge follows its member's carrier with a delay - only
                # resume once its own link event is queued as well
                self.wait_for_result(
                    lambda: read_file(f'/sys/class/net/{client}/operstate'), link_state)
                sleep(1)
            finally:
                rc_cmd(f'sudo kill -CONT {netlinkd_pid}')

        self._t9675_setup()
        try:
            self._t9675_wait_leases((True, True, True))
            start = int(time())

            queued('down', '2001:db8:96ff:ffff::1')
            self.wait_for_result(lambda: self._unit_state(dhclient), 'inactive')
            self.assertEqual(self._unit_state(dhclient), 'inactive')

            queued('up', '2001:db8:96ff:ffff::2')
            self._t9675_wait_leases((True, True, True))
            self.assertEqual(self._unit_state(dhclient), 'active')

            _, log = rc_cmd(f'sudo journalctl --no-pager --output=cat '
                            f'--identifier=vyos-netlinkd --since=@{start}')
            self.assertNotIn(f'Reconcile {client}:', log)
        finally:
            rc_cmd(f'sudo kill -CONT {netlinkd_pid}')
            self._t9675_teardown()

    def test_dhcp_clients_admin_down(self):
        # An administratively disabled interface stops both DHCP clients and
        # removes their leases, re-enabling it brings both back
        client = self._t9675_client
        client_path = ['interfaces', 'bridge', client]
        dhclient, dhcp6c = f'dhclient@{client}.service', f'dhcp6c@{client}.service'

        self._t9675_setup()
        try:
            self._t9675_wait_leases((True, True, True))

            self.cli_set(client_path + ['disable'])
            self.cli_commit()
            self.assertEqual(self._unit_state(dhclient), 'inactive')
            self.assertEqual(self._unit_state(dhcp6c), 'inactive')
            self._t9675_wait_leases((False, False, False))

            self.cli_delete(client_path + ['disable'])
            self.cli_commit()
            self._t9675_wait_leases((True, True, True))
            self.assertEqual(self._unit_state(dhclient), 'active')
            self.assertEqual(self._unit_state(dhcp6c), 'active')
        finally:
            self._t9675_teardown()

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
