#!/usr/bin/env python3
#
# Copyright (C) 2021-2022 VyOS maintainers and contributors
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
from vyos.template import is_ipv6
from vyos.util import process_named_running

PROCESS_NAME = 'bgpd'
ASN = '64512'
base_path = ['protocols', 'bgp']

route_map_in = 'foo-map-in'
route_map_out = 'foo-map-out'
prefix_list_in = 'pfx-foo-in'
prefix_list_out = 'pfx-foo-out'
prefix_list_in6 = 'pfx-foo-in6'
prefix_list_out6 = 'pfx-foo-out6'
bfd_profile = 'foo-bar-baz'

neighbor_config = {
    '192.0.2.1' : {
        'bfd'              : '',
        'cap_dynamic'      : '',
        'cap_ext_next'     : '',
        'remote_as'        : '100',
        'adv_interv'       : '400',
        'passive'          : '',
        'password'         : 'VyOS-Secure123',
        'shutdown'         : '',
        'cap_over'         : '',
        'ttl_security'     : '5',
        'local_as'         : '300',
        'route_map_in'     : route_map_in,
        'route_map_out'    : route_map_out,
        'no_send_comm_ext' : '',
        'addpath_all'      : '',
        },
    '192.0.2.2' : {
        'bfd_profile'      : bfd_profile,
        'remote_as'        : '200',
        'shutdown'         : '',
        'no_cap_nego'      : '',
        'port'             : '667',
        'cap_strict'       : '',
        'advertise_map'    : route_map_in,
        'non_exist_map'    : route_map_out,
        'pfx_list_in'      : prefix_list_in,
        'pfx_list_out'     : prefix_list_out,
        'no_send_comm_std' : '',
        },
    '192.0.2.3' : {
        'advertise_map'    : route_map_in,
        'description'      : 'foo bar baz',
        'remote_as'        : '200',
        'passive'          : '',
        'multi_hop'        : '5',
        'update_src'       : 'lo',
        'peer_group'       : 'foo',
        'graceful_rst'     : '',
        },
    '2001:db8::1' : {
        'advertise_map'    : route_map_in,
        'exist_map'        : route_map_out,
        'cap_dynamic'      : '',
        'cap_ext_next'     : '',
        'remote_as'        : '123',
        'adv_interv'       : '400',
        'passive'          : '',
        'password'         : 'VyOS-Secure123',
        'shutdown'         : '',
        'cap_over'         : '',
        'ttl_security'     : '5',
        'local_as'         : '300',
        'solo'             : '',
        'route_map_in'     : route_map_in,
        'route_map_out'    : route_map_out,
        'no_send_comm_std' : '',
        'addpath_per_as'   : '',
        'peer_group'       : 'foo-bar',
        },
    '2001:db8::2' : {
        'remote_as'        : '456',
        'shutdown'         : '',
        'no_cap_nego'      : '',
        'port'             : '667',
        'cap_strict'       : '',
        'pfx_list_in'      : prefix_list_in6,
        'pfx_list_out'     : prefix_list_out6,
        'no_send_comm_ext' : '',
        'peer_group'       : 'foo-bar_baz',
        'graceful_rst_hlp' : ''
        },
}

peer_group_config = {
    'foo' : {
        'advertise_map'    : route_map_in,
        'exist_map'        : route_map_out,
        'bfd'              : '',
        'remote_as'        : '100',
        'passive'          : '',
        'password'         : 'VyOS-Secure123',
        'shutdown'         : '',
        'cap_over'         : '',
        'ttl_security'     : '5',
        },
    'bar' : {
        'remote_as'        : '111',
        'graceful_rst_no'  : ''
        },
    'foo-bar' : {
        'advertise_map'    : route_map_in,
        'description'      : 'foo peer bar group',
        'remote_as'        : '200',
        'shutdown'         : '',
        'no_cap_nego'      : '',
        'local_as'         : '300',
        'pfx_list_in'      : prefix_list_in,
        'pfx_list_out'     : prefix_list_out,
        'no_send_comm_ext' : '',
        },
    'foo-bar_baz' : {
        'advertise_map'    : route_map_in,
        'non_exist_map'    : route_map_out,
        'bfd_profile'      : bfd_profile,
        'cap_dynamic'      : '',
        'cap_ext_next'     : '',
        'remote_as'        : '200',
        'passive'          : '',
        'multi_hop'        : '5',
        'update_src'       : 'lo',
        'route_map_in'     : route_map_in,
        'route_map_out'    : route_map_out,
        },
}

class TestProtocolsBGP(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProtocolsBGP, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

        cls.cli_set(cls, ['policy', 'route-map', route_map_in, 'rule', '10', 'action', 'permit'])
        cls.cli_set(cls, ['policy', 'route-map', route_map_out, 'rule', '10', 'action', 'permit'])
        cls.cli_set(cls, ['policy', 'prefix-list', prefix_list_in, 'rule', '10', 'action', 'permit'])
        cls.cli_set(cls, ['policy', 'prefix-list', prefix_list_in, 'rule', '10', 'prefix', '192.0.2.0/25'])
        cls.cli_set(cls, ['policy', 'prefix-list', prefix_list_out, 'rule', '10', 'action', 'permit'])
        cls.cli_set(cls, ['policy', 'prefix-list', prefix_list_out, 'rule', '10', 'prefix', '192.0.2.128/25'])

        cls.cli_set(cls, ['policy', 'prefix-list6', prefix_list_in6, 'rule', '10', 'action', 'permit'])
        cls.cli_set(cls, ['policy', 'prefix-list6', prefix_list_in6, 'rule', '10', 'prefix', '2001:db8:1000::/64'])
        cls.cli_set(cls, ['policy', 'prefix-list6', prefix_list_out6, 'rule', '10', 'action', 'deny'])
        cls.cli_set(cls, ['policy', 'prefix-list6', prefix_list_out6, 'rule', '10', 'prefix', '2001:db8:2000::/64'])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['policy'])

    def setUp(self):
        self.cli_set(base_path + ['local-as', ASN])

    def tearDown(self):
        self.cli_delete(['vrf'])
        self.cli_delete(base_path)
        self.cli_commit()

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def verify_frr_config(self, peer, peer_config, frrconfig):
        # recurring patterns to verify for both a simple neighbor and a peer-group
        if 'bfd' in peer_config:
            self.assertIn(f' neighbor {peer} bfd', frrconfig)
        if 'bfd_profile' in peer_config:
            self.assertIn(f' neighbor {peer} bfd profile {peer_config["bfd_profile"]}', frrconfig)
            self.assertIn(f' neighbor {peer} bfd check-control-plane-failure', frrconfig)
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
            self.assertIn(f' neighbor {peer} local-as {peer_config["local_as"]} no-prepend replace-as', frrconfig)
        if 'cap_over' in peer_config:
            self.assertIn(f' neighbor {peer} override-capability', frrconfig)
        if 'passive' in peer_config:
            self.assertIn(f' neighbor {peer} passive', frrconfig)
        if 'password' in peer_config:
            self.assertIn(f' neighbor {peer} password {peer_config["password"]}', frrconfig)
        if 'remote_as' in peer_config:
            self.assertIn(f' neighbor {peer} remote-as {peer_config["remote_as"]}', frrconfig)
        if 'solo' in peer_config:
            self.assertIn(f' neighbor {peer} solo', frrconfig)
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
        if 'advertise_map' in peer_config:
            base = f' neighbor {peer} advertise-map {peer_config["advertise_map"]}'
            if 'exist_map' in peer_config:
                base = f'{base} exist-map {peer_config["exist_map"]}'
            if 'non_exist_map' in peer_config:
                base = f'{base} non-exist-map {peer_config["non_exist_map"]}'
            self.assertIn(base, frrconfig)
        if 'graceful_rst' in peer_config:
            self.assertIn(f' neighbor {peer} graceful-restart', frrconfig)
        if 'graceful_rst_no' in peer_config:
            self.assertIn(f' neighbor {peer} graceful-restart-disable', frrconfig)
        if 'graceful_rst_hlp' in peer_config:
            self.assertIn(f' neighbor {peer} graceful-restart-helper', frrconfig)

    def test_bgp_01_simple(self):
        router_id = '127.0.0.1'
        local_pref = '500'
        stalepath_time = '60'
        max_path_v4 = '2'
        max_path_v4ibgp = '4'
        max_path_v6 = '8'
        max_path_v6ibgp = '16'
        cond_adv_timer = '30'
        min_hold_time = '2'

        self.cli_set(base_path + ['parameters', 'router-id', router_id])
        self.cli_set(base_path + ['parameters', 'log-neighbor-changes'])

        # Local AS number MUST be defined - as this is set in setUp() we remove
        # this once for testing of the proper error
        self.cli_delete(base_path + ['local-as'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['local-as', ASN])

        # Default local preference (higher = more preferred, default value is 100)
        self.cli_set(base_path + ['parameters', 'default', 'local-pref', local_pref])
        self.cli_set(base_path + ['parameters', 'graceful-restart', 'stalepath-time', stalepath_time])
        self.cli_set(base_path + ['parameters', 'graceful-shutdown'])
        self.cli_set(base_path + ['parameters', 'ebgp-requires-policy'])

        self.cli_set(base_path + ['parameters', 'bestpath', 'as-path', 'multipath-relax'])
        self.cli_set(base_path + ['parameters', 'bestpath', 'bandwidth', 'default-weight-for-missing'])
        self.cli_set(base_path + ['parameters', 'bestpath', 'compare-routerid'])

        self.cli_set(base_path + ['parameters', 'conditional-advertisement', 'timer', cond_adv_timer])
        self.cli_set(base_path + ['parameters', 'fast-convergence'])
        self.cli_set(base_path + ['parameters', 'minimum-holdtime', min_hold_time])
        self.cli_set(base_path + ['parameters', 'no-suppress-duplicates'])
        self.cli_set(base_path + ['parameters', 'reject-as-sets'])
        self.cli_set(base_path + ['parameters', 'shutdown'])
        self.cli_set(base_path + ['parameters', 'suppress-fib-pending'])

        # AFI maximum path support
        self.cli_set(base_path + ['address-family', 'ipv4-unicast', 'maximum-paths', 'ebgp', max_path_v4])
        self.cli_set(base_path + ['address-family', 'ipv4-unicast', 'maximum-paths', 'ibgp', max_path_v4ibgp])
        self.cli_set(base_path + ['address-family', 'ipv6-unicast', 'maximum-paths', 'ebgp', max_path_v6])
        self.cli_set(base_path + ['address-family', 'ipv6-unicast', 'maximum-paths', 'ibgp', max_path_v6ibgp])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' bgp router-id {router_id}', frrconfig)
        self.assertIn(f' bgp log-neighbor-changes', frrconfig)
        self.assertIn(f' bgp default local-preference {local_pref}', frrconfig)
        self.assertIn(f' bgp conditional-advertisement timer {cond_adv_timer}', frrconfig)
        self.assertIn(f' bgp fast-convergence', frrconfig)
        self.assertIn(f' bgp graceful-restart stalepath-time {stalepath_time}', frrconfig)
        self.assertIn(f' bgp graceful-shutdown', frrconfig)
        self.assertIn(f' bgp bestpath as-path multipath-relax', frrconfig)
        self.assertIn(f' bgp bestpath bandwidth default-weight-for-missing', frrconfig)
        self.assertIn(f' bgp bestpath compare-routerid', frrconfig)
        self.assertIn(f' bgp minimum-holdtime {min_hold_time}', frrconfig)
        self.assertIn(f' bgp reject-as-sets', frrconfig)
        self.assertIn(f' bgp shutdown', frrconfig)
        self.assertIn(f' bgp suppress-fib-pending', frrconfig)
        self.assertNotIn(f'bgp ebgp-requires-policy', frrconfig)
        self.assertIn(f' no bgp suppress-duplicates', frrconfig)

        afiv4_config = self.getFRRconfig(' address-family ipv4 unicast')
        self.assertIn(f'  maximum-paths {max_path_v4}', afiv4_config)
        self.assertIn(f'  maximum-paths ibgp {max_path_v4ibgp}', afiv4_config)

        afiv6_config = self.getFRRconfig(' address-family ipv6 unicast')
        self.assertIn(f'  maximum-paths {max_path_v6}', afiv6_config)
        self.assertIn(f'  maximum-paths ibgp {max_path_v6ibgp}', afiv6_config)


    def test_bgp_02_neighbors(self):
        # Test out individual neighbor configuration items, not all of them are
        # also available to a peer-group!
        self.cli_set(base_path + ['parameters', 'deterministic-med'])

        for peer, peer_config in neighbor_config.items():
            afi = 'ipv4-unicast'
            if is_ipv6(peer):
                afi = 'ipv6-unicast'

            if 'adv_interv' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'advertisement-interval', peer_config["adv_interv"]])
            if 'bfd' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'bfd'])
            if 'bfd_profile' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'bfd', 'profile', peer_config["bfd_profile"]])
                self.cli_set(base_path + ['neighbor', peer, 'bfd', 'check-control-plane-failure'])
            if 'cap_dynamic' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'capability', 'dynamic'])
            if 'cap_ext_next' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'capability', 'extended-nexthop'])
            if 'description' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'description', peer_config["description"]])
            if 'no_cap_nego' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'disable-capability-negotiation'])
            if 'multi_hop' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'ebgp-multihop', peer_config["multi_hop"]])
            if 'local_as' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'local-as', peer_config["local_as"], 'no-prepend', 'replace-as'])
            if 'cap_over' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'override-capability'])
            if 'passive' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'passive'])
            if 'password' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'password', peer_config["password"]])
            if 'port' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'port', peer_config["port"]])
            if 'remote_as' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'remote-as', peer_config["remote_as"]])
            if 'cap_strict' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'strict-capability-match'])
            if 'shutdown' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'shutdown'])
            if 'solo' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'solo'])
            if 'ttl_security' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'ttl-security', 'hops', peer_config["ttl_security"]])
            if 'update_src' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'update-source', peer_config["update_src"]])
            if 'route_map_in' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'address-family', afi, 'route-map', 'import', peer_config["route_map_in"]])
            if 'route_map_out' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'address-family', afi, 'route-map', 'export', peer_config["route_map_out"]])
            if 'pfx_list_in' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'address-family', afi, 'prefix-list', 'import', peer_config["pfx_list_in"]])
            if 'pfx_list_out' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'address-family', afi, 'prefix-list', 'export', peer_config["pfx_list_out"]])
            if 'no_send_comm_std' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'address-family', afi, 'disable-send-community', 'standard'])
            if 'no_send_comm_ext' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'address-family', afi, 'disable-send-community', 'extended'])
            if 'addpath_all' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'address-family', afi, 'addpath-tx-all'])
            if 'addpath_per_as' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'address-family', afi, 'addpath-tx-per-as'])
            if 'graceful_rst' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'graceful-restart', 'enable'])
            if 'graceful_rst_no' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'graceful-restart', 'disable'])
            if 'graceful_rst_hlp' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'graceful-restart', 'restart-helper'])

            # Conditional advertisement
            if 'advertise_map' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'address-family', afi, 'conditionally-advertise', 'advertise-map', peer_config["advertise_map"]])
                # Either exist-map or non-exist-map needs to be specified
                if 'exist_map' not in peer_config and 'non_exist_map' not in peer_config:
                    with self.assertRaises(ConfigSessionError):
                        self.cli_commit()
                    self.cli_set(base_path + ['neighbor', peer, 'address-family', afi, 'conditionally-advertise', 'exist-map', route_map_in])

                if 'exist_map' in peer_config:
                    self.cli_set(base_path + ['neighbor', peer, 'address-family', afi, 'conditionally-advertise', 'exist-map', peer_config["exist_map"]])
                if 'non_exist_map' in peer_config:
                    self.cli_set(base_path + ['neighbor', peer, 'address-family', afi, 'conditionally-advertise', 'non-exist-map', peer_config["non_exist_map"]])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
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
            if 'bfd' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'bfd'])
            if 'bfd_profile' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'bfd', 'profile', config["bfd_profile"]])
                self.cli_set(base_path + ['peer-group', peer_group, 'bfd', 'check-control-plane-failure'])
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
                self.cli_set(base_path + ['peer-group', peer_group, 'local-as', config["local_as"], 'no-prepend', 'replace-as'])
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
            if 'route_map_in' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'route-map', 'import', config["route_map_in"]])
            if 'route_map_out' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'route-map', 'export', config["route_map_out"]])
            if 'pfx_list_in' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'prefix-list', 'import', config["pfx_list_in"]])
            if 'pfx_list_out' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'prefix-list', 'export', config["pfx_list_out"]])
            if 'no_send_comm_std' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'disable-send-community', 'standard'])
            if 'no_send_comm_ext' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'disable-send-community', 'extended'])
            if 'addpath_all' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'addpath-tx-all'])
            if 'addpath_per_as' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'addpath-tx-per-as'])
            if 'graceful_rst' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'graceful-restart', 'enable'])
            if 'graceful_rst_no' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'graceful-restart', 'disable'])
            if 'graceful_rst_hlp' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'graceful-restart', 'restart-helper'])

            # Conditional advertisement
            if 'advertise_map' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'conditionally-advertise', 'advertise-map', config["advertise_map"]])
                # Either exist-map or non-exist-map needs to be specified
                if 'exist_map' not in config and 'non_exist_map' not in config:
                    with self.assertRaises(ConfigSessionError):
                        self.cli_commit()
                    self.cli_set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'conditionally-advertise', 'exist-map', route_map_in])

                if 'exist_map' in config:
                    self.cli_set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'conditionally-advertise', 'exist-map', config["exist_map"]])
                if 'non_exist_map' in config:
                    self.cli_set(base_path + ['peer-group', peer_group, 'address-family', 'ipv4-unicast', 'conditionally-advertise', 'non-exist-map', config["non_exist_map"]])

        for peer, peer_config in neighbor_config.items():
            if 'peer_group' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'peer-group', peer_config['peer_group']])


        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)

        for peer, peer_config in peer_group_config.items():
            self.assertIn(f' neighbor {peer_group} peer-group', frrconfig)
            self.verify_frr_config(peer, peer_config, frrconfig)

        for peer, peer_config in neighbor_config.items():
            if 'peer_group' in peer_config:
                self.assertIn(f' neighbor {peer} peer-group {peer_config["peer_group"]}', frrconfig)


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
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
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
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
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

        self.cli_set(base_path + ['listen', 'limit', limit])

        for prefix in listen_ranges:
            self.cli_set(base_path + ['listen', 'range', prefix])
            # check validate() - peer-group must be defined for range/prefix
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_set(base_path + ['listen', 'range', prefix, 'peer-group', peer_group])

        # check validate() - peer-group does yet not exist!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['peer-group', peer_group, 'remote-as', ASN])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' neighbor {peer_group} peer-group', frrconfig)
        self.assertIn(f' neighbor {peer_group} remote-as {ASN}', frrconfig)
        self.assertIn(f' bgp listen limit {limit}', frrconfig)
        for prefix in listen_ranges:
            self.assertIn(f' bgp listen range {prefix} peer-group {peer_group}', frrconfig)


    def test_bgp_07_l2vpn_evpn(self):
        vnis = ['10010', '10020', '10030']
        neighbors = ['192.0.2.10', '192.0.2.20', '192.0.2.30']

        self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'advertise-all-vni'])
        self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'advertise-default-gw'])
        self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'advertise-svi-ip'])
        self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'flooding', 'disable'])
        for vni in vnis:
            self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'vni', vni, 'advertise-default-gw'])
            self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'vni', vni, 'advertise-svi-ip'])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' address-family l2vpn evpn', frrconfig)
        self.assertIn(f'  advertise-all-vni', frrconfig)
        self.assertIn(f'  advertise-default-gw', frrconfig)
        self.assertIn(f'  advertise-svi-ip', frrconfig)
        self.assertIn(f'  flooding disable', frrconfig)
        for vni in vnis:
            vniconfig = self.getFRRconfig(f'  vni {vni}')
            self.assertIn(f'vni {vni}', vniconfig)
            self.assertIn(f'   advertise-default-gw', vniconfig)
            self.assertIn(f'   advertise-svi-ip', vniconfig)

    def test_bgp_08_zebra_route_map(self):
        # Implemented because of T3328
        self.cli_set(base_path + ['route-map', route_map_in])
        # commit changes
        self.cli_commit()

        # Verify FRR configuration
        zebra_route_map = f'ip protocol bgp route-map {route_map_in}'
        frrconfig = self.getFRRconfig(zebra_route_map)
        self.assertIn(zebra_route_map, frrconfig)

        # Remove the route-map again
        self.cli_delete(base_path + ['route-map'])
        # commit changes
        self.cli_commit()

        # Verify FRR configuration
        frrconfig = self.getFRRconfig(zebra_route_map)
        self.assertNotIn(zebra_route_map, frrconfig)

    def test_bgp_09_distance_and_flowspec(self):
        distance_external = '25'
        distance_internal = '30'
        distance_local = '35'
        distance_v4_prefix = '169.254.0.0/32'
        distance_v6_prefix = '2001::/128'
        distance_prefix_value = '110'
        distance_families = ['ipv4-unicast', 'ipv6-unicast','ipv4-multicast', 'ipv6-multicast']
        verify_families = ['ipv4 unicast', 'ipv6 unicast','ipv4 multicast', 'ipv6 multicast']
        flowspec_families = ['address-family ipv4 flowspec', 'address-family ipv6 flowspec']
        flowspec_int = 'lo'

        # Per family distance support
        for family in distance_families:
            self.cli_set(base_path + ['address-family', family, 'distance', 'external', distance_external])
            self.cli_set(base_path + ['address-family', family, 'distance', 'internal', distance_internal])
            self.cli_set(base_path + ['address-family', family, 'distance', 'local', distance_local])
            if 'ipv4' in family:
                self.cli_set(base_path + ['address-family', family, 'distance',
                                          'prefix', distance_v4_prefix, 'distance', distance_prefix_value])
            if 'ipv6' in family:
                self.cli_set(base_path + ['address-family', family, 'distance',
                                          'prefix', distance_v6_prefix, 'distance', distance_prefix_value])

        # IPv4 flowspec interface check
        self.cli_set(base_path + ['address-family', 'ipv4-flowspec', 'local-install', 'interface', flowspec_int])

        # IPv6 flowspec interface check
        self.cli_set(base_path + ['address-family', 'ipv6-flowspec', 'local-install', 'interface', flowspec_int])

        # Commit changes
        self.cli_commit()

        # Verify FRR distances configuration
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        for family in verify_families:
            self.assertIn(f'address-family {family}', frrconfig)
            self.assertIn(f'distance bgp {distance_external} {distance_internal} {distance_local}', frrconfig)
            if 'ipv4' in family:
                self.assertIn(f'distance {distance_prefix_value} {distance_v4_prefix}', frrconfig)
            if 'ipv6' in family:
                self.assertIn(f'distance {distance_prefix_value} {distance_v6_prefix}', frrconfig)

        # Verify FRR flowspec configuration
        for family in flowspec_families:
            self.assertIn(f'{family}', frrconfig)
            self.assertIn(f'local-install {flowspec_int}', frrconfig)


    def test_bgp_10_vrf_simple(self):
        router_id = '127.0.0.3'
        vrfs = ['red', 'green', 'blue']

        # It is safe to assume that when the basic VRF test works, all
        # other BGP related features work, as we entirely inherit the CLI
        # templates and Jinja2 FRR template.
        table = '1000'

        self.cli_set(base_path + ['local-as', ASN])
        # testing only one AFI is sufficient as it's generic code

        for vrf in vrfs:
            vrf_base = ['vrf', 'name', vrf]
            self.cli_set(vrf_base + ['table', table])
            self.cli_set(vrf_base + ['protocols', 'bgp', 'local-as', ASN])
            self.cli_set(vrf_base + ['protocols', 'bgp', 'parameters', 'router-id', router_id])
            self.cli_set(vrf_base + ['protocols', 'bgp', 'route-map', route_map_in])
            table = str(int(table) + 1000)

            # import VRF routes do main RIB
            self.cli_set(base_path + ['address-family', 'ipv6-unicast', 'import', 'vrf', vrf])

        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' address-family ipv6 unicast', frrconfig)


        for vrf in vrfs:
            self.assertIn(f'  import vrf {vrf}', frrconfig)

            # Verify FRR bgpd configuration
            frr_vrf_config = self.getFRRconfig(f'router bgp {ASN} vrf {vrf}')
            self.assertIn(f'router bgp {ASN} vrf {vrf}', frr_vrf_config)
            self.assertIn(f' bgp router-id {router_id}', frr_vrf_config)

            # XXX: Currently this is not working as FRR() class does not support
            # route-maps for multiple vrfs because the modify_section() only works
            # on lines and not text blocks.
            #
            # vrfconfig = self.getFRRconfig(f'vrf {vrf}')
            # zebra_route_map = f' ip protocol bgp route-map {route_map_in}'
            # self.assertIn(zebra_route_map, vrfconfig)


    def test_bgp_11_confederation(self):
        router_id = '127.10.10.2'
        confed_id = str(int(ASN) + 1)
        confed_asns = '10 20 30 40'

        self.cli_set(base_path + ['local-as', ASN])
        self.cli_set(base_path + ['parameters', 'router-id', router_id])
        self.cli_set(base_path + ['parameters', 'confederation', 'identifier', confed_id])
        for asn in confed_asns.split():
            self.cli_set(base_path + ['parameters', 'confederation', 'peers', asn])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' bgp router-id {router_id}', frrconfig)
        self.assertIn(f' bgp confederation identifier {confed_id}', frrconfig)
        self.assertIn(f' bgp confederation peers {confed_asns}', frrconfig)


    def test_bgp_12_v6_link_local(self):
        remote_asn = str(int(ASN) + 10)
        interface = 'eth0'

        self.cli_set(base_path + ['local-as', ASN])
        self.cli_set(base_path + ['neighbor', interface, 'address-family', 'ipv6-unicast'])
        self.cli_set(base_path + ['neighbor', interface, 'interface', 'v6only', 'remote-as', remote_asn])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' neighbor {interface} interface v6only remote-as {remote_asn}', frrconfig)
        self.assertIn(f' address-family ipv6 unicast', frrconfig)
        self.assertIn(f'  neighbor {interface} activate', frrconfig)
        self.assertIn(f' exit-address-family', frrconfig)


    def test_bgp_13_vpn(self):
        remote_asn = str(int(ASN) + 150)
        neighbor = '192.0.2.55'
        vrf_name = 'red'
        label = 'auto'
        rd = f'{neighbor}:{ASN}'
        rt_export = f'{neighbor}:1002 1.2.3.4:567'
        rt_import = f'{neighbor}:1003 500:100'

        self.cli_set(base_path + ['local-as', ASN])
        # testing only one AFI is sufficient as it's generic code
        for afi in ['ipv4-unicast', 'ipv6-unicast']:
            self.cli_set(base_path + ['address-family', afi, 'export', 'vpn'])
            self.cli_set(base_path + ['address-family', afi, 'import', 'vpn'])
            self.cli_set(base_path + ['address-family', afi, 'label', 'vpn', 'export', label])
            self.cli_set(base_path + ['address-family', afi, 'rd', 'vpn', 'export', rd])
            self.cli_set(base_path + ['address-family', afi, 'route-map', 'vpn', 'export', route_map_out])
            self.cli_set(base_path + ['address-family', afi, 'route-map', 'vpn', 'import', route_map_in])
            self.cli_set(base_path + ['address-family', afi, 'route-target', 'vpn', 'export', rt_export])
            self.cli_set(base_path + ['address-family', afi, 'route-target', 'vpn', 'import', rt_import])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)

        for afi in ['ipv4', 'ipv6']:
            afi_config = self.getFRRconfig(f' address-family {afi} unicast', endsection='exit-address-family', daemon='bgpd')
            self.assertIn(f'address-family {afi} unicast', afi_config)
            self.assertIn(f'  export vpn', afi_config)
            self.assertIn(f'  import vpn', afi_config)
            self.assertIn(f'  label vpn export {label}', afi_config)
            self.assertIn(f'  rd vpn export {rd}', afi_config)
            self.assertIn(f'  route-map vpn export {route_map_out}', afi_config)
            self.assertIn(f'  route-map vpn import {route_map_in}', afi_config)
            self.assertIn(f'  rt vpn export {rt_export}', afi_config)
            self.assertIn(f'  rt vpn import {rt_import}', afi_config)
            self.assertIn(f' exit-address-family', afi_config)

    def test_bgp_14_remote_as_peer_group_override(self):
        # Peer-group member cannot override remote-as of peer-group
        remote_asn = str(int(ASN) + 150)
        neighbor = '192.0.2.1'
        peer_group = 'bar'
        interface = 'eth0'

        self.cli_set(base_path + ['local-as', ASN])
        self.cli_set(base_path + ['neighbor', neighbor, 'remote-as', remote_asn])
        self.cli_set(base_path + ['neighbor', neighbor, 'peer-group', peer_group])
        self.cli_set(base_path + ['peer-group', peer_group, 'remote-as', remote_asn])

        # Peer-group member cannot override remote-as of peer-group
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['neighbor', neighbor, 'remote-as'])

        # re-test with interface based peer-group
        self.cli_set(base_path + ['neighbor', interface, 'interface', 'peer-group', peer_group])
        self.cli_set(base_path + ['neighbor', interface, 'interface', 'remote-as', 'external'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['neighbor', interface, 'interface', 'remote-as'])

        # re-test with interface based v6only peer-group
        self.cli_set(base_path + ['neighbor', interface, 'interface', 'v6only', 'peer-group', peer_group])
        self.cli_set(base_path + ['neighbor', interface, 'interface', 'v6only', 'remote-as', 'external'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['neighbor', interface, 'interface', 'v6only', 'remote-as'])

        self.cli_commit()

        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' neighbor {neighbor} peer-group {peer_group}', frrconfig)
        self.assertIn(f' neighbor {peer_group} peer-group', frrconfig)
        self.assertIn(f' neighbor {peer_group} remote-as {remote_asn}', frrconfig)

if __name__ == '__main__':
    unittest.main(verbosity=2)
