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

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.template import is_ipv6
from vyos.util import cmd
from vyos.util import process_named_running

PROCESS_NAME = 'bgpd'
ASN = '64512'
base_path = ['protocols', 'bgp', ASN]

route_map_in = 'foo-map-in'
route_map_out = 'foo-map-out'
prefix_list_in = 'pfx-foo-in'
prefix_list_out = 'pfx-foo-out'
prefix_list_in6 = 'pfx-foo-in6'
prefix_list_out6 = 'pfx-foo-out6'

neighbor_config = {
    '192.0.2.1' : {
        'cap_dynamic'  : '',
        'cap_ext_next' : '',
        'remote_as'    : '100',
        'adv_interv'   : '400',
        'passive'      : '',
        'password'     : 'VyOS-Secure123',
        'shutdown'     : '',
        'cap_over'     : '',
        'ttl_security' : '5',
        'local_as'     : '300',
        'route_map_in' : route_map_in,
        'route_map_out': route_map_out,
        'no_send_comm_ext' : '',
        'addpath_all' : '',
        },
    '192.0.2.2' : {
        'remote_as'    : '200',
        'shutdown'     : '',
        'no_cap_nego'  : '',
        'port'         : '667',
        'cap_strict'   : '',
        'pfx_list_in'  : prefix_list_in,
        'pfx_list_out' : prefix_list_out,
        'no_send_comm_std' : '',
        },
    '192.0.2.3' : {
        'description'  : 'foo bar baz',
        'remote_as'    : '200',
        'passive'      : '',
        'multi_hop'    : '5',
        'update_src'   : 'lo',
        },
    '2001:db8::1' : {
        'cap_dynamic'  : '',
        'cap_ext_next' : '',
        'remote_as'    : '123',
        'adv_interv'   : '400',
        'passive'      : '',
        'password'     : 'VyOS-Secure123',
        'shutdown'     : '',
        'cap_over'     : '',
        'ttl_security' : '5',
        'local_as'     : '300',
        'route_map_in' : route_map_in,
        'route_map_out': route_map_out,
        'no_send_comm_std' : '',
        'addpath_per_as'   : '',
        },
    '2001:db8::2' : {
        'remote_as'    : '456',
        'shutdown'     : '',
        'no_cap_nego'  : '',
        'port'         : '667',
        'cap_strict'   : '',
        'pfx_list_in'  : prefix_list_in6,
        'pfx_list_out' : prefix_list_out6,
        'no_send_comm_ext' : '',
        },
}

peer_group_config = {
    'foo' : {
        'remote_as'    : '100',
        'passive'      : '',
        'password'     : 'VyOS-Secure123',
        'shutdown'     : '',
        'cap_over'     : '',
#        XXX: not available in current Perl backend
#       'ttl_security': '5',
        },
    'bar' : {
        'description'  : 'foo peer bar group',
        'remote_as'    : '200',
        'shutdown'     : '',
        'no_cap_nego'  : '',
        'local_as'     : '300',
        'pfx_list_in'  : prefix_list_in,
        'pfx_list_out' : prefix_list_out,
        'no_send_comm_ext' : '',
        },
    'baz' : {
        'cap_dynamic'  : '',
        'cap_ext_next' : '',
        'remote_as'    : '200',
        'passive'      : '',
        'multi_hop'    : '5',
        'update_src'   : 'lo',
        'route_map_in' : route_map_in,
        'route_map_out': route_map_out,
        },
}

def getFRRBGPconfig():
    return cmd(f'vtysh -c "show run" | sed -n "/^router bgp {ASN}/,/^!/p"')

def getFRRBgpAfiConfig(afi):
    return cmd(f'vtysh -c "show run" | sed -n "/^router bgp {ASN}/,/^!/p" | sed -n "/^ address-family {afi} unicast/,/^ exit-address-family/p"')

def getFRRBGPVNIconfig(vni):
    return cmd(f'vtysh -c "show run" | sed -n "/^  vni {vni}/,/^!/p"')

def getFRRRPKIconfig():
    return cmd(f'vtysh -c "show run" | sed -n "/^rpki/,/^!/p"')

class TestProtocolsBGP(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())

        self.session.set(['policy', 'route-map', route_map_in, 'rule', '10', 'action', 'permit'])
        self.session.set(['policy', 'route-map', route_map_out, 'rule', '10', 'action', 'permit'])
        self.session.set(['policy', 'prefix-list', prefix_list_in, 'rule', '10', 'action', 'permit'])
        self.session.set(['policy', 'prefix-list', prefix_list_in, 'rule', '10', 'prefix', '192.0.2.0/25'])
        self.session.set(['policy', 'prefix-list', prefix_list_out, 'rule', '10', 'action', 'permit'])
        self.session.set(['policy', 'prefix-list', prefix_list_out, 'rule', '10', 'prefix', '192.0.2.128/25'])

        self.session.set(['policy', 'prefix-list6', prefix_list_in6, 'rule', '10', 'action', 'permit'])
        self.session.set(['policy', 'prefix-list6', prefix_list_in6, 'rule', '10', 'prefix', '2001:db8:1000::/64'])
        self.session.set(['policy', 'prefix-list6', prefix_list_out6, 'rule', '10', 'action', 'deny'])
        self.session.set(['policy', 'prefix-list6', prefix_list_out6, 'rule', '10', 'prefix', '2001:db8:2000::/64'])

    def tearDown(self):
        self.session.delete(['policy', 'route-map', route_map_in])
        self.session.delete(['policy', 'route-map', route_map_out])
        self.session.delete(['policy', 'prefix-list', prefix_list_in])
        self.session.delete(['policy', 'prefix-list', prefix_list_out])
        self.session.delete(['policy', 'prefix-list6', prefix_list_in6])
        self.session.delete(['policy', 'prefix-list6', prefix_list_out6])

        self.session.delete(base_path)
        self.session.commit()
        del self.session

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

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
        if 'route_map_in' in peer_config:
            self.assertIn(f' neighbor {peer} route-map {peer_config["route_map_in"]} in', frrconfig)
        if 'route_map_out' in peer_config:
            self.assertIn(f' neighbor {peer} route-map {peer_config["route_map_out"]} out', frrconfig)
        if 'pfx_list_in' in peer_config:
            self.assertIn(f' neighbor {peer} prefix-list {peer_config["pfx_list_in"]} in', frrconfig)
        if 'pfx_list_out' in peer_config:
            self.assertIn(f' neighbor {peer} prefix-list {peer_config["pfx_list_out"]} out', frrconfig)
        if 'no_send_comm_std' in peer_config:
            self.assertIn(f' no neighbor {peer} send-community', frrconfig)
        if 'no_send_comm_ext' in peer_config:
            self.assertIn(f' no neighbor {peer} send-community extended', frrconfig)
        if 'addpath_all' in peer_config:
            self.assertIn(f' neighbor {peer} addpath-tx-all-paths', frrconfig)
        if 'addpath_per_as' in peer_config:
            self.assertIn(f' neighbor {peer} addpath-tx-bestpath-per-AS', frrconfig)


    def test_bgp_01_simple(self):
        router_id = '127.0.0.1'
        local_pref = '500'
        stalepath_time = '60'
        max_path_v4 = '2'
        max_path_v4ibgp = '4'
        max_path_v6 = '8'
        max_path_v6ibgp = '16'

        self.session.set(base_path + ['parameters', 'router-id', router_id])
        self.session.set(base_path + ['parameters', 'log-neighbor-changes'])
        # Default local preference (higher = more preferred, default value is 100)
        self.session.set(base_path + ['parameters', 'default', 'local-pref', local_pref])
        # Deactivate IPv4 unicast for a peer by default
        self.session.set(base_path + ['parameters', 'default', 'no-ipv4-unicast'])
        self.session.set(base_path + ['parameters', 'graceful-restart', 'stalepath-time', stalepath_time])
        self.session.set(base_path + ['parameters', 'graceful-shutdown'])
        self.session.set(base_path + ['parameters', 'ebgp-requires-policy'])

        # AFI maximum path support
        self.session.set(base_path + ['address-family', 'ipv4-unicast', 'maximum-paths', max_path_v4])
        self.session.set(base_path + ['address-family', 'ipv4-unicast', 'maximum-paths-ibgp', max_path_v4ibgp])
        self.session.set(base_path + ['address-family', 'ipv6-unicast', 'maximum-paths', max_path_v6])
        self.session.set(base_path + ['address-family', 'ipv6-unicast', 'maximum-paths-ibgp', max_path_v6ibgp])

        # commit changes
        self.session.commit()

        # Verify FRR bgpd configuration
        frrconfig = getFRRBGPconfig()
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' bgp router-id {router_id}', frrconfig)
        self.assertIn(f' bgp log-neighbor-changes', frrconfig)
        self.assertIn(f' bgp default local-preference {local_pref}', frrconfig)
        self.assertIn(f' no bgp default ipv4-unicast', frrconfig)
        self.assertIn(f' bgp graceful-restart stalepath-time {stalepath_time}', frrconfig)
        self.assertIn(f' bgp graceful-shutdown', frrconfig)
        self.assertNotIn(f'bgp ebgp-requires-policy', frrconfig)

        afiv4_config = getFRRBgpAfiConfig('ipv4')
        self.assertIn(f'  maximum-paths {max_path_v4}', afiv4_config)
        self.assertIn(f'  maximum-paths ibgp {max_path_v4ibgp}', afiv4_config)

        afiv6_config = getFRRBgpAfiConfig('ipv6')
        self.assertIn(f'  maximum-paths {max_path_v6}', afiv6_config)
        self.assertIn(f'  maximum-paths ibgp {max_path_v6ibgp}', afiv6_config)


    def test_bgp_02_neighbors(self):
        # Test out individual neighbor configuration items, not all of them are
        # also available to a peer-group!
        for peer, peer_config in neighbor_config.items():
            afi = 'ipv4-unicast'
            if is_ipv6(peer):
                afi = 'ipv6-unicast'

            if 'adv_interv' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'advertisement-interval', peer_config["adv_interv"]])
            if 'cap_dynamic' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'capability', 'dynamic'])
            if 'cap_ext_next' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'capability', 'extended-nexthop'])
            if 'description' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'description', peer_config["description"]])
            if 'no_cap_nego' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'disable-capability-negotiation'])
            if 'multi_hop' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'ebgp-multihop', peer_config["multi_hop"]])
            if 'local_as' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'local-as', peer_config["local_as"]])
            if 'cap_over' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'override-capability'])
            if 'passive' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'passive'])
            if 'password' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'password', peer_config["password"]])
            if 'port' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'port', peer_config["port"]])
            if 'remote_as' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'remote-as', peer_config["remote_as"]])
            if 'cap_strict' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'strict-capability-match'])
            if 'shutdown' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'shutdown'])
            if 'ttl_security' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'ttl-security', 'hops', peer_config["ttl_security"]])
            if 'update_src' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'update-source', peer_config["update_src"]])
            if 'route_map_in' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'address-family', afi, 'route-map', 'import', peer_config["route_map_in"]])
            if 'route_map_out' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'address-family', afi, 'route-map', 'export', peer_config["route_map_out"]])
            if 'pfx_list_in' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'address-family', afi, 'prefix-list', 'import', peer_config["pfx_list_in"]])
            if 'pfx_list_out' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'address-family', afi, 'prefix-list', 'export', peer_config["pfx_list_out"]])
            if 'no_send_comm_std' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'address-family', afi, 'disable-send-community', 'standard'])
            if 'no_send_comm_ext' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'address-family', afi, 'disable-send-community', 'extended'])
            if 'addpath_all' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'address-family', afi, 'addpath-tx-all'])
            if 'addpath_per_as' in peer_config:
                self.session.set(base_path + ['neighbor', peer, 'address-family', afi, 'addpath-tx-per-as'])

        # commit changes
        self.session.commit()

        # Verify FRR bgpd configuration
        frrconfig = getFRRBGPconfig()
        self.assertIn(f'router bgp {ASN}', frrconfig)

        for peer, peer_config in neighbor_config.items():
            if 'adv_interv' in peer_config:
                self.assertIn(f' neighbor {peer} advertisement-interval {peer_config["adv_interv"]}', frrconfig)
            if 'port' in peer_config:
                self.assertIn(f' neighbor {peer} port {peer_config["port"]}', frrconfig)
            if 'cap_strict' in peer_config:
                self.assertIn(f' neighbor {peer} strict-capability-match', frrconfig)

            self.verify_frr_config(peer, peer_config, frrconfig)

    def test_bgp_03_peer_groups(self):
        # Test out individual peer-group configuration items
        for peer_group, config in peer_group_config.items():
            if 'cap_dynamic' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'capability', 'dynamic'])
            if 'cap_ext_next' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'capability', 'extended-nexthop'])
            if 'description' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'description', config["description"]])
            if 'no_cap_nego' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'disable-capability-negotiation'])
            if 'multi_hop' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'ebgp-multihop', config["multi_hop"]])
            if 'local_as' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'local-as', config["local_as"]])
            if 'cap_over' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'override-capability'])
            if 'passive' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'passive'])
            if 'password' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'password', config["password"]])
            if 'remote_as' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'remote-as', config["remote_as"]])
            if 'shutdown' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'shutdown'])
            if 'ttl_security' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'ttl-security', 'hops', config["ttl_security"]])
            if 'update_src' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'update-source', config["update_src"]])
            if 'route_map_in' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'route-map', 'import', config["route_map_in"]])
            if 'route_map_out' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'route-map', 'export', config["route_map_out"]])
            if 'pfx_list_in' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'prefix-list', 'import', config["pfx_list_in"]])
            if 'pfx_list_out' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'prefix-list', 'export', config["pfx_list_out"]])
            if 'no_send_comm_std' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'disable-send-community', 'standard'])
            if 'no_send_comm_ext' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'disable-send-community', 'extended'])
            if 'addpath_all' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'addpath-tx-all'])
            if 'addpath_per_as' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'addpath-tx-per-as'])

        # commit changes
        self.session.commit()

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
            self.session.set(base_path + ['address-family', 'ipv4-unicast',
                                          'redistribute', redistribute])

        for network, network_config in networks.items():
            self.session.set(base_path + ['address-family', 'ipv4-unicast',
                                          'network', network])
            if 'as_set' in network_config:
                self.session.set(base_path + ['address-family', 'ipv4-unicast',
                                              'aggregate-address', network, 'as-set'])
            if 'summary_only' in network_config:
                self.session.set(base_path + ['address-family', 'ipv4-unicast',
                                              'aggregate-address', network, 'summary-only'])

        # commit changes
        self.session.commit()

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
            self.session.set(base_path + ['address-family', 'ipv6-unicast',
                                          'redistribute', redistribute])

        for network, network_config in networks.items():
            self.session.set(base_path + ['address-family', 'ipv6-unicast',
                                          'network', network])
            if 'summary_only' in network_config:
                self.session.set(base_path + ['address-family', 'ipv6-unicast',
                                              'aggregate-address', network, 'summary-only'])

        # commit changes
        self.session.commit()

        # Verify FRR bgpd configuration
        frrconfig = getFRRBGPconfig()
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' address-family ipv6 unicast', frrconfig)
        # T2100: By default ebgp-requires-policy is disabled to keep VyOS
        # 1.3 and 1.2 backwards compatibility
        self.assertIn(f' no bgp ebgp-requires-policy', frrconfig)

        for redistribute in redistributes:
            # FRR calls this OSPF6
            if redistribute == 'ospfv3':
                redistribute = 'ospf6'
            self.assertIn(f' redistribute {redistribute}', frrconfig)

        for network, network_config in networks.items():
            self.assertIn(f' network {network}', frrconfig)
            if 'as_set' in network_config:
                self.assertIn(f' aggregate-address {network} summary-only', frrconfig)


    def test_bgp_06_listen_range(self):
        # Implemented via T1875
        limit = '64'
        listen_ranges = ['192.0.2.0/25', '192.0.2.128/25']
        peer_group = 'listenfoobar'
        self.session.set(base_path + ['listen', 'limit', limit])
        for prefix in listen_ranges:
            self.session.set(base_path + ['listen', 'range', prefix])
            # check validate() - peer-group must be defined for range/prefix
            with self.assertRaises(ConfigSessionError):
                self.session.commit()
            self.session.set(base_path + ['listen', 'range', prefix, 'peer-group', peer_group])

        # check validate() - peer-group does yet not exist!
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(base_path + ['peer-group', peer_group, 'remote-as', ASN])

        # commit changes
        self.session.commit()

        # Verify FRR bgpd configuration
        frrconfig = getFRRBGPconfig()
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' neighbor {peer_group} peer-group', frrconfig)
        self.assertIn(f' neighbor {peer_group} remote-as {ASN}', frrconfig)
        self.assertIn(f' bgp listen limit {limit}', frrconfig)
        for prefix in listen_ranges:
            self.assertIn(f' bgp listen range {prefix} peer-group {peer_group}', frrconfig)


    def test_bgp_07_l2vpn_evpn(self):
        vnis = ['10010', '10020', '10030']
        neighbors = ['192.0.2.10', '192.0.2.20', '192.0.2.30']
        self.session.set(base_path + ['address-family', 'l2vpn-evpn', 'advertise-all-vni'])
        self.session.set(base_path + ['address-family', 'l2vpn-evpn', 'advertise-default-gw'])
        self.session.set(base_path + ['address-family', 'l2vpn-evpn', 'advertise-svi-ip'])
        self.session.set(base_path + ['address-family', 'l2vpn-evpn', 'flooding', 'disable'])
        for vni in vnis:
            self.session.set(base_path + ['address-family', 'l2vpn-evpn', 'vni', vni, 'advertise-default-gw'])
            self.session.set(base_path + ['address-family', 'l2vpn-evpn', 'vni', vni, 'advertise-svi-ip'])

        # commit changes
        self.session.commit()

        # Verify FRR bgpd configuration
        frrconfig = getFRRBGPconfig()
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' address-family l2vpn evpn', frrconfig)
        self.assertIn(f'  advertise-all-vni', frrconfig)
        self.assertIn(f'  advertise-default-gw', frrconfig)
        self.assertIn(f'  advertise-svi-ip', frrconfig)
        self.assertIn(f'  flooding disable', frrconfig)
        for vni in vnis:
            vniconfig = getFRRBGPVNIconfig(vni)
            self.assertIn(f'vni {vni}', vniconfig)
            self.assertIn(f'   advertise-default-gw', vniconfig)
            self.assertIn(f'   advertise-svi-ip', vniconfig)

if __name__ == '__main__':
    unittest.main(verbosity=2)
