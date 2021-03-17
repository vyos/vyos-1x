#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

import os
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import cmd
from vyos.util import process_named_running

PROCESS_NAME = 'bgpd'
ASN = '64512'
base_path = ['protocols', 'bgp', ASN]

neighbor_config = {
    '192.0.2.1' : {
        'cap_dynamic' : '',
        'cap_ext_next': '',
        'remote_as'   : '100',
        'adv_interv'  : '400',
        'passive'     : '',
        'password'    : 'VyOS-Secure123',
        'shutdown'    : '',
        'cap_over'    : '',
        'ttl_security': '5',
        'local_as'    : '300',
        },
    '192.0.2.2' : {
        'remote_as'   : '200',
        'shutdown'    : '',
        'no_cap_nego' : '',
        'port'        : '667',
        'cap_strict'  : '',
        },
    '192.0.2.3' : {
#        XXX: not available in current Perl backend
#       'description' : 'foo bar baz',
        'remote_as'   : '200',
        'passive'     : '',
        'multi_hop'   : '5',
        'update_src'  : 'lo',
        },
}

peer_group_config = {
    'foo' : {
        'remote_as'   : '100',
        'passive'     : '',
        'password'    : 'VyOS-Secure123',
        'shutdown'    : '',
        'cap_over'    : '',
#        XXX: not available in current Perl backend
#       'ttl_security': '5',
        },
    'bar' : {
#        XXX: not available in current Perl backend
#       'description' : 'foo peer bar group',
        'remote_as'   : '200',
        'shutdown'    : '',
        'no_cap_nego' : '',
        'local_as'    : '300',
        },
    'baz' : {
        'cap_dynamic' : '',
        'cap_ext_next': '',
        'remote_as'   : '200',
        'passive'     : '',
        'multi_hop'   : '5',
        'update_src'  : 'lo',
        },
}

def getFRRBGPconfig():
    return cmd(f'vtysh -c "show run" | sed -n "/router bgp {ASN}/,/^!/p"')

class TestProtocolsBGP(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def verify_frr_config(self, peer, peer_config, frrconfig):
        # recurring patterns to verify for both a simple neighbor and a peer-group
        if 'cap_dynamic' in peer_config:
            self.assertIn(f' neighbor {peer} capability dynamic', frrconfig)
        if 'cap_ext_next' in peer_config:
            self.assertIn(f' neighbor {peer} capability extended-nexthop', frrconfig)
        if 'description' in peer_config:
            self.assertIn(f' neighbor {peer} description {peer_config["description"]}', frrconfig)
        if 'no_cap_nego' in peer_config:
            self.assertIn(f' neighbor {peer} dont-capability-negotiate', frrconfig)
        if 'multi_hop' in peer_config:
            self.assertIn(f' neighbor {peer} ebgp-multihop {peer_config["multi_hop"]}', frrconfig)
        if 'local_as' in peer_config:
            self.assertIn(f' neighbor {peer} local-as {peer_config["local_as"]}', frrconfig)
        if 'cap_over' in peer_config:
            self.assertIn(f' neighbor {peer} override-capability', frrconfig)
        if 'passive' in peer_config:
            self.assertIn(f' neighbor {peer} passive', frrconfig)
        if 'password' in peer_config:
            self.assertIn(f' neighbor {peer} password {peer_config["password"]}', frrconfig)
        if 'remote_as' in peer_config:
            self.assertIn(f' neighbor {peer} remote-as {peer_config["remote_as"]}', frrconfig)
        if 'shutdown' in peer_config:
            self.assertIn(f' neighbor {peer} shutdown', frrconfig)
        if 'ttl_security' in peer_config:
            self.assertIn(f' neighbor {peer} ttl-security hops {peer_config["ttl_security"]}', frrconfig)
        if 'update_src' in peer_config:
            self.assertIn(f' neighbor {peer} update-source {peer_config["update_src"]}', frrconfig)

    def test_bgp_01_simple(self):
        router_id = '127.0.0.1'
        local_pref = '500'

        self.cli_set(base_path + ['parameters', 'router-id', router_id])
        self.cli_set(base_path + ['parameters', 'log-neighbor-changes'])
        # Default local preference (higher=more preferred)
        self.cli_set(base_path + ['parameters', 'default', 'local-pref', local_pref])
        # Deactivate IPv4 unicast for a peer by default
        self.cli_set(base_path + ['parameters', 'default', 'no-ipv4-unicast'])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = getFRRBGPconfig()
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' bgp router-id {router_id}', frrconfig)
        self.assertIn(f' bgp log-neighbor-changes', frrconfig)
        self.assertIn(f' bgp default local-preference {local_pref}', frrconfig)
        self.assertIn(f' no bgp default ipv4-unicast', frrconfig)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_bgp_02_neighbors(self):
        # Test out individual neighbor configuration items, not all of them are
        # also available to a peer-group!
        for neighbor, config in neighbor_config.items():
            if 'adv_interv' in config:
                self.cli_set(base_path + ['neighbor', neighbor, 'advertisement-interval', config["adv_interv"]])
            if 'cap_dynamic' in config:
                self.cli_set(base_path + ['neighbor', neighbor, 'capability', 'dynamic'])
            if 'cap_ext_next' in config:
                self.cli_set(base_path + ['neighbor', neighbor, 'capability', 'extended-nexthop'])
            if 'description' in config:
                self.cli_set(base_path + ['neighbor', neighbor, 'description', config["description"]])
            if 'no_cap_nego' in config:
                self.cli_set(base_path + ['neighbor', neighbor, 'disable-capability-negotiation'])
            if 'multi_hop' in config:
                self.cli_set(base_path + ['neighbor', neighbor, 'ebgp-multihop', config["multi_hop"]])
            if 'local_as' in config:
                self.cli_set(base_path + ['neighbor', neighbor, 'local-as', config["local_as"]])
            if 'cap_over' in config:
                self.cli_set(base_path + ['neighbor', neighbor, 'override-capability'])
            if 'passive' in config:
                self.cli_set(base_path + ['neighbor', neighbor, 'passive'])
            if 'password' in config:
                self.cli_set(base_path + ['neighbor', neighbor, 'password', config["password"]])
            if 'port' in config:
                self.cli_set(base_path + ['neighbor', neighbor, 'port', config["port"]])
            if 'remote_as' in config:
                self.cli_set(base_path + ['neighbor', neighbor, 'remote-as', config["remote_as"]])
            if 'cap_strict' in config:
                self.cli_set(base_path + ['neighbor', neighbor, 'strict-capability-match'])
            if 'shutdown' in config:
                self.cli_set(base_path + ['neighbor', neighbor, 'shutdown'])
            if 'ttl_security' in config:
                self.cli_set(base_path + ['neighbor', neighbor, 'ttl-security', 'hops', config["ttl_security"]])
            if 'update_src' in config:
                self.cli_set(base_path + ['neighbor', neighbor, 'update-source', config["update_src"]])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = getFRRBGPconfig()
        self.assertIn(f'router bgp {ASN}', frrconfig)

        for peer, peer_config in neighbor_config.items():
            if 'adv_interv' in config:
                self.assertIn(f' neighbor {peer} advertisement-interval {peer_config["adv_interv"]}', frrconfig)
            if 'port' in config:
                self.assertIn(f' neighbor {peer} port {peer_config["port"]}', frrconfig)
            if 'cap_strict' in config:
                self.assertIn(f' neighbor {peer} strict-capability-match', frrconfig)

            self.verify_frr_config(peer, peer_config, frrconfig)

    def test_bgp_03_peer_groups(self):
        # Test out individual peer-group configuration items
        for peer_group, config in peer_group_config.items():
            if 'cap_dynamic' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'capability', 'dynamic'])
            if 'cap_ext_next' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'capability', 'extended-nexthop'])
            if 'description' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'description', config["description"]])
            if 'no_cap_nego' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'disable-capability-negotiation'])
            if 'multi_hop' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'ebgp-multihop', config["multi_hop"]])
            if 'local_as' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'local-as', config["local_as"]])
            if 'cap_over' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'override-capability'])
            if 'passive' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'passive'])
            if 'password' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'password', config["password"]])
            if 'remote_as' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'remote-as', config["remote_as"]])
            if 'shutdown' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'shutdown'])
            if 'ttl_security' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'ttl-security', 'hops', config["ttl_security"]])
            if 'update_src' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'update-source', config["update_src"]])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = getFRRBGPconfig()
        self.assertIn(f'router bgp {ASN}', frrconfig)

        for peer, peer_config in peer_group_config.items():
            self.assertIn(f' neighbor {peer_group} peer-group', frrconfig)
            self.verify_frr_config(peer, peer_config, frrconfig)


    def test_bgp_04_afi_ipv4(self):
        networks = {
            '10.0.0.0/8' : {
                'as_set' : '',
                },
            '100.64.0.0/10' : {
                'as_set' : '',
                },
            '192.168.0.0/16' : {
                'summary_only' : '',
                },
        }

        # We want to redistribute ...
        redistributes = ['connected', 'isis', 'kernel', 'ospf', 'rip', 'static']
        for redistribute in redistributes:
            self.cli_set(base_path + ['address-family', 'ipv4-unicast',
                                          'redistribute', redistribute])

        for network, network_config in networks.items():
            self.cli_set(base_path + ['address-family', 'ipv4-unicast',
                                          'network', network])
            if 'as_set' in network_config:
                self.cli_set(base_path + ['address-family', 'ipv4-unicast',
                                              'aggregate-address', network, 'as-set'])
            if 'summary_only' in network_config:
                self.cli_set(base_path + ['address-family', 'ipv4-unicast',
                                              'aggregate-address', network, 'summary-only'])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = getFRRBGPconfig()
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' address-family ipv4 unicast', frrconfig)

        for redistribute in redistributes:
            self.assertIn(f' redistribute {redistribute}', frrconfig)

        for network, network_config in networks.items():
            self.assertIn(f' network {network}', frrconfig)
            if 'as_set' in network_config:
                self.assertIn(f' aggregate-address {network} as-set', frrconfig)
            if 'summary_only' in network_config:
                self.assertIn(f' aggregate-address {network} summary-only', frrconfig)


    def test_bgp_05_afi_ipv6(self):
        networks = {
            '2001:db8:100::/48' : {
                },
            '2001:db8:200::/48' : {
                },
            '2001:db8:300::/48' : {
                'summary_only' : '',
                },
        }

        # We want to redistribute ...
        redistributes = ['connected', 'kernel', 'ospfv3', 'ripng', 'static']
        for redistribute in redistributes:
            self.cli_set(base_path + ['address-family', 'ipv6-unicast',
                                          'redistribute', redistribute])

        for network, network_config in networks.items():
            self.cli_set(base_path + ['address-family', 'ipv6-unicast',
                                          'network', network])
            if 'summary_only' in network_config:
                self.cli_set(base_path + ['address-family', 'ipv6-unicast',
                                              'aggregate-address', network, 'summary-only'])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = getFRRBGPconfig()
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' address-family ipv6 unicast', frrconfig)

        for redistribute in redistributes:
            # FRR calls this OSPF6
            if redistribute == 'ospfv3':
                redistribute = 'ospf6'
            self.assertIn(f' redistribute {redistribute}', frrconfig)

        for network, network_config in networks.items():
            self.assertIn(f' network {network}', frrconfig)
            if 'as_set' in network_config:
                self.assertIn(f' aggregate-address {network} summary-only', frrconfig)


if __name__ == '__main__':
    unittest.main(verbosity=2)
