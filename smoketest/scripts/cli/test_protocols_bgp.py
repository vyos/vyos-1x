#!/usr/bin/env python3
#
# Copyright (C) 2021-2023 VyOS maintainers and contributors
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

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.ifconfig import Section
from vyos.configsession import ConfigSessionError
from vyos.template import is_ipv6
from vyos.utils.process import process_named_running
from vyos.utils.process import cmd

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

import_afi = 'ipv4-unicast'
import_vrf = 'red'
import_rd = ASN + ':100'
import_vrf_base = ['vrf', 'name']
neighbor_config = {
    '192.0.2.1' : {
        'bfd'              : '',
        'cap_dynamic'      : '',
        'cap_ext_next'     : '',
        'cap_ext_sver'     : '',
        'remote_as'        : '100',
        'adv_interv'       : '400',
        'passive'          : '',
        'password'         : 'VyOS-Secure123',
        'shutdown'         : '',
        'cap_over'         : '',
        'ttl_security'     : '5',
        'system_as'        : '300',
        'route_map_in'     : route_map_in,
        'route_map_out'    : route_map_out,
        'no_send_comm_ext' : '',
        'addpath_all'      : '',
        'p_attr_discard'   : ['10', '20', '30', '40', '50'],
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
        'local_role'       : 'rs-client',
        'p_attr_taw'       : '200',
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
        'cap_ext_sver'     : '',
        'remote_as'        : '123',
        'adv_interv'       : '400',
        'passive'          : '',
        'password'         : 'VyOS-Secure123',
        'shutdown'         : '',
        'cap_over'         : '',
        'ttl_security'     : '5',
        'system_as'        : '300',
        'solo'             : '',
        'route_map_in'     : route_map_in,
        'route_map_out'    : route_map_out,
        'no_send_comm_std' : '',
        'addpath_per_as'   : '',
        'peer_group'       : 'foo-bar',
        'local_role'       : 'customer',
        'local_role_strict': '',
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
        'graceful_rst_hlp' : '',
        'disable_conn_chk' : '',
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
        'disable_conn_chk' : '',
        'p_attr_discard'   : ['100', '150', '200'],
        },
    'bar' : {
        'remote_as'        : '111',
        'graceful_rst_no'  : '',
        'port'             : '667',
        'p_attr_taw'       : '126',
        },
    'foo-bar' : {
        'advertise_map'    : route_map_in,
        'description'      : 'foo peer bar group',
        'remote_as'        : '200',
        'shutdown'         : '',
        'no_cap_nego'      : '',
        'system_as'        : '300',
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
        'local_role'       : 'peer',
        'local_role_strict': '',
        },
}
class TestProtocolsBGP(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProtocolsBGP, cls).setUpClass()

        # Retrieve FRR daemon PID - it is not allowed to crash, thus PID must remain the same
        cls.daemon_pid = process_named_running(PROCESS_NAME)

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)
        cls.cli_delete(cls, ['policy', 'route-map'])
        cls.cli_delete(cls, ['policy', 'prefix-list'])
        cls.cli_delete(cls, ['policy', 'prefix-list6'])
        cls.cli_delete(cls, ['vrf'])

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
        cls.cli_delete(cls, ['policy', 'route-map'])
        cls.cli_delete(cls, ['policy', 'prefix-list'])
        cls.cli_delete(cls, ['policy', 'prefix-list6'])

    def setUp(self):
        self.cli_set(base_path + ['system-as', ASN])

    def tearDown(self):
        # cleanup any possible VRF mess
        self.cli_delete(['vrf'])
        # always destrox the entire bgpd configuration to make the processes
        # life as hard as possible
        self.cli_delete(base_path)
        self.cli_commit()

        # check process health and continuity
        self.assertEqual(self.daemon_pid, process_named_running(PROCESS_NAME))

    def create_bgp_instances_for_import_test(self):
        table = '1000'
        self.cli_set(import_vrf_base + [import_vrf, 'table', table])
        self.cli_set(import_vrf_base + [import_vrf, 'protocols', 'bgp', 'system-as', ASN])

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
        if 'cap_ext_sver' in peer_config:
            self.assertIn(f' neighbor {peer} capability software-version', frrconfig)
        if 'description' in peer_config:
            self.assertIn(f' neighbor {peer} description {peer_config["description"]}', frrconfig)
        if 'no_cap_nego' in peer_config:
            self.assertIn(f' neighbor {peer} dont-capability-negotiate', frrconfig)
        if 'multi_hop' in peer_config:
            self.assertIn(f' neighbor {peer} ebgp-multihop {peer_config["multi_hop"]}', frrconfig)
        if 'local_as' in peer_config:
            self.assertIn(f' neighbor {peer} local-as {peer_config["local_as"]} no-prepend replace-as', frrconfig)
        if 'local_role' in peer_config:
            tmp = f' neighbor {peer} local-role {peer_config["local_role"]}'
            if 'local_role_strict' in peer_config:
                tmp += ' strict'
            self.assertIn(tmp, frrconfig)
        if 'cap_over' in peer_config:
            self.assertIn(f' neighbor {peer} override-capability', frrconfig)
        if 'passive' in peer_config:
            self.assertIn(f' neighbor {peer} passive', frrconfig)
        if 'password' in peer_config:
            self.assertIn(f' neighbor {peer} password {peer_config["password"]}', frrconfig)
        if 'port' in peer_config:
            self.assertIn(f' neighbor {peer} port {peer_config["port"]}', frrconfig)
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
        if 'p_attr_discard' in peer_config:
            tmp = ' '.join(peer_config["p_attr_discard"])
            self.assertIn(f' neighbor {peer} path-attribute discard {tmp}', frrconfig)
        if 'p_attr_taw' in peer_config:
            self.assertIn(f' neighbor {peer} path-attribute treat-as-withdraw {peer_config["p_attr_taw"]}', frrconfig)
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
        if 'disable_conn_chk' in peer_config:
            self.assertIn(f' neighbor {peer} disable-connected-check', frrconfig)

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
        tcp_keepalive_idle = '66'
        tcp_keepalive_interval = '77'
        tcp_keepalive_probes = '22'

        self.cli_set(base_path + ['parameters', 'allow-martian-nexthop'])
        self.cli_set(base_path + ['parameters', 'disable-ebgp-connected-route-check'])
        self.cli_set(base_path + ['parameters', 'no-hard-administrative-reset'])
        self.cli_set(base_path + ['parameters', 'log-neighbor-changes'])
        self.cli_set(base_path + ['parameters', 'labeled-unicast', 'explicit-null'])
        self.cli_set(base_path + ['parameters', 'router-id', router_id])

        # System AS number MUST be defined - as this is set in setUp() we remove
        # this once for testing of the proper error
        self.cli_delete(base_path + ['system-as'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['system-as', ASN])

        # Default local preference (higher = more preferred, default value is 100)
        self.cli_set(base_path + ['parameters', 'default', 'local-pref', local_pref])
        self.cli_set(base_path + ['parameters', 'graceful-restart', 'stalepath-time', stalepath_time])
        self.cli_set(base_path + ['parameters', 'graceful-shutdown'])
        self.cli_set(base_path + ['parameters', 'ebgp-requires-policy'])

        self.cli_set(base_path + ['parameters', 'bestpath', 'as-path', 'multipath-relax'])
        self.cli_set(base_path + ['parameters', 'bestpath', 'bandwidth', 'default-weight-for-missing'])
        self.cli_set(base_path + ['parameters', 'bestpath', 'compare-routerid'])
        self.cli_set(base_path + ['parameters', 'bestpath', 'peer-type', 'multipath-relax'])

        self.cli_set(base_path + ['parameters', 'conditional-advertisement', 'timer', cond_adv_timer])
        self.cli_set(base_path + ['parameters', 'fast-convergence'])
        self.cli_set(base_path + ['parameters', 'minimum-holdtime', min_hold_time])
        self.cli_set(base_path + ['parameters', 'no-suppress-duplicates'])
        self.cli_set(base_path + ['parameters', 'reject-as-sets'])
        self.cli_set(base_path + ['parameters', 'route-reflector-allow-outbound-policy'])
        self.cli_set(base_path + ['parameters', 'shutdown'])
        self.cli_set(base_path + ['parameters', 'suppress-fib-pending'])
        self.cli_set(base_path + ['parameters', 'tcp-keepalive', 'idle', tcp_keepalive_idle])
        self.cli_set(base_path + ['parameters', 'tcp-keepalive', 'interval', tcp_keepalive_interval])
        self.cli_set(base_path + ['parameters', 'tcp-keepalive', 'probes', tcp_keepalive_probes])

        # AFI maximum path support
        self.cli_set(base_path + ['address-family', 'ipv4-unicast', 'maximum-paths', 'ebgp', max_path_v4])
        self.cli_set(base_path + ['address-family', 'ipv4-unicast', 'maximum-paths', 'ibgp', max_path_v4ibgp])
        self.cli_set(base_path + ['address-family', 'ipv4-labeled-unicast', 'maximum-paths', 'ebgp', max_path_v4])
        self.cli_set(base_path + ['address-family', 'ipv4-labeled-unicast', 'maximum-paths', 'ibgp', max_path_v4ibgp])
        self.cli_set(base_path + ['address-family', 'ipv6-unicast', 'maximum-paths', 'ebgp', max_path_v6])
        self.cli_set(base_path + ['address-family', 'ipv6-unicast', 'maximum-paths', 'ibgp', max_path_v6ibgp])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' bgp router-id {router_id}', frrconfig)
        self.assertIn(f' bgp allow-martian-nexthop', frrconfig)
        self.assertIn(f' bgp disable-ebgp-connected-route-check', frrconfig)
        self.assertIn(f' bgp log-neighbor-changes', frrconfig)
        self.assertIn(f' bgp default local-preference {local_pref}', frrconfig)
        self.assertIn(f' bgp conditional-advertisement timer {cond_adv_timer}', frrconfig)
        self.assertIn(f' bgp fast-convergence', frrconfig)
        self.assertIn(f' bgp graceful-restart stalepath-time {stalepath_time}', frrconfig)
        self.assertIn(f' bgp graceful-shutdown', frrconfig)
        self.assertIn(f' no bgp hard-administrative-reset', frrconfig)
        self.assertIn(f' bgp labeled-unicast explicit-null', frrconfig)
        self.assertIn(f' bgp bestpath as-path multipath-relax', frrconfig)
        self.assertIn(f' bgp bestpath bandwidth default-weight-for-missing', frrconfig)
        self.assertIn(f' bgp bestpath compare-routerid', frrconfig)
        self.assertIn(f' bgp bestpath peer-type multipath-relax', frrconfig)
        self.assertIn(f' bgp minimum-holdtime {min_hold_time}', frrconfig)
        self.assertIn(f' bgp reject-as-sets', frrconfig)
        self.assertIn(f' bgp route-reflector allow-outbound-policy', frrconfig)
        self.assertIn(f' bgp shutdown', frrconfig)
        self.assertIn(f' bgp suppress-fib-pending', frrconfig)
        self.assertIn(f' bgp tcp-keepalive {tcp_keepalive_idle} {tcp_keepalive_interval} {tcp_keepalive_probes}', frrconfig)
        self.assertNotIn(f'bgp ebgp-requires-policy', frrconfig)
        self.assertIn(f' no bgp suppress-duplicates', frrconfig)

        afiv4_config = self.getFRRconfig(' address-family ipv4 unicast')
        self.assertIn(f'  maximum-paths {max_path_v4}', afiv4_config)
        self.assertIn(f'  maximum-paths ibgp {max_path_v4ibgp}', afiv4_config)

        afiv4_config = self.getFRRconfig(' address-family ipv4 labeled-unicast')
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
            if 'cap_ext_sver' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'capability', 'software-version'])
            if 'description' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'description', peer_config["description"]])
            if 'no_cap_nego' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'disable-capability-negotiation'])
            if 'multi_hop' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'ebgp-multihop', peer_config["multi_hop"]])
            if 'local_as' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'local-as', peer_config["local_as"], 'no-prepend', 'replace-as'])
            if 'local_role' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'local-role', peer_config["local_role"]])
                if 'local_role_strict' in peer_config:
                    self.cli_set(base_path + ['neighbor', peer, 'local-role', peer_config["local_role"], 'strict'])
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
            if 'p_attr_discard' in peer_config:
                for attribute in peer_config['p_attr_discard']:
                    self.cli_set(base_path + ['neighbor', peer, 'path-attribute', 'discard', attribute])
            if 'p_attr_taw' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'path-attribute', 'treat-as-withdraw', peer_config["p_attr_taw"]])
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
            if 'disable_conn_chk' in peer_config:
                self.cli_set(base_path + ['neighbor', peer, 'disable-connected-check'])

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
            if 'cap_ext_sver' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'capability', 'software-version'])
            if 'description' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'description', config["description"]])
            if 'no_cap_nego' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'disable-capability-negotiation'])
            if 'multi_hop' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'ebgp-multihop', config["multi_hop"]])
            if 'local_as' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'local-as', config["local_as"], 'no-prepend', 'replace-as'])
            if 'local_role' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'local-role', config["local_role"]])
                if 'local_role_strict' in config:
                    self.cli_set(base_path + ['peer-group', peer_group, 'local-role', config["local_role"], 'strict'])
            if 'cap_over' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'override-capability'])
            if 'passive' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'passive'])
            if 'password' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'password', config["password"]])
            if 'port' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'port', config["port"]])
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
            if 'disable_conn_chk' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'disable-connected-check'])
            if 'p_attr_discard' in config:
                for attribute in config['p_attr_discard']:
                    self.cli_set(base_path + ['peer-group', peer_group, 'path-attribute', 'discard', attribute])
            if 'p_attr_taw' in config:
                self.cli_set(base_path + ['peer-group', peer_group, 'path-attribute', 'treat-as-withdraw', config["p_attr_taw"]])

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
                'summary_only' : '',
                'route_map' : route_map_in,
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
            if 'route_map' in network_config:
                self.cli_set(base_path + ['address-family', 'ipv4-unicast',
                                              'aggregate-address', network, 'route-map', network_config['route_map']])

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
            command = f'aggregate-address {network}'
            if 'as_set' in network_config:
                command = f'{command} as-set'
            if 'summary_only' in network_config:
                command = f'{command} summary-only'
            if 'route_map' in network_config:
                command = f'{command} route-map {network_config["route_map"]}'
            self.assertIn(command, frrconfig)

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
        soo = '1.2.3.4:10000'
        evi_limit = '1000'
        route_targets = ['1.1.1.1:100', '1.1.1.1:200', '1.1.1.1:300']

        self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'advertise-all-vni'])
        self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'advertise-default-gw'])
        self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'advertise-svi-ip'])
        self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'flooding', 'disable'])
        self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'default-originate', 'ipv4'])
        self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'default-originate', 'ipv6'])
        self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'disable-ead-evi-rx'])
        self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'disable-ead-evi-tx'])
        self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'mac-vrf', 'soo', soo])
        for vni in vnis:
            self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'vni', vni, 'advertise-default-gw'])
            self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'vni', vni, 'advertise-svi-ip'])

        self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'ead-es-frag', 'evi-limit', evi_limit])
        for route_target in route_targets:
            self.cli_set(base_path + ['address-family', 'l2vpn-evpn', 'ead-es-route-target', 'export', route_target])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' address-family l2vpn evpn', frrconfig)
        self.assertIn(f'  advertise-all-vni', frrconfig)
        self.assertIn(f'  advertise-default-gw', frrconfig)
        self.assertIn(f'  advertise-svi-ip', frrconfig)
        self.assertIn(f'  default-originate ipv4', frrconfig)
        self.assertIn(f'  default-originate ipv6', frrconfig)
        self.assertIn(f'  disable-ead-evi-rx', frrconfig)
        self.assertIn(f'  disable-ead-evi-tx', frrconfig)
        self.assertIn(f'  flooding disable', frrconfig)
        self.assertIn(f'  mac-vrf soo {soo}', frrconfig)
        for vni in vnis:
            vniconfig = self.getFRRconfig(f'  vni {vni}')
            self.assertIn(f'vni {vni}', vniconfig)
            self.assertIn(f'   advertise-default-gw', vniconfig)
            self.assertIn(f'   advertise-svi-ip', vniconfig)
        self.assertIn(f'  ead-es-frag evi-limit {evi_limit}', frrconfig)
        for route_target in route_targets:
            self.assertIn(f'  ead-es-route-target export {route_target}', frrconfig)


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

        # testing only one AFI is sufficient as it's generic code
        for vrf in vrfs:
            vrf_base = ['vrf', 'name', vrf]
            self.cli_set(vrf_base + ['table', table])
            self.cli_set(vrf_base + ['protocols', 'bgp', 'system-as', ASN])
            self.cli_set(vrf_base + ['protocols', 'bgp', 'parameters', 'router-id', router_id])
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

    def test_bgp_11_confederation(self):
        router_id = '127.10.10.2'
        confed_id = str(int(ASN) + 1)
        confed_asns = '10 20 30 40'

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

        # testing only one AFI is sufficient as it's generic code
        for afi in ['ipv4-unicast', 'ipv6-unicast']:
            self.cli_set(base_path + ['address-family', afi, 'export', 'vpn'])
            self.cli_set(base_path + ['address-family', afi, 'import', 'vpn'])
            self.cli_set(base_path + ['address-family', afi, 'label', 'vpn', 'export', label])
            self.cli_set(base_path + ['address-family', afi, 'label', 'vpn', 'allocation-mode', 'per-nexthop'])
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
            self.assertIn(f'  label vpn export allocation-mode per-nexthop', afi_config)
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

    def test_bgp_15_local_as_ebgp(self):
        # https://vyos.dev/T4560
        # local-as allowed only for ebgp peers

        neighbor = '192.0.2.99'
        remote_asn = '500'
        local_asn = '400'

        self.cli_set(base_path + ['neighbor', neighbor, 'remote-as', ASN])
        self.cli_set(base_path + ['neighbor', neighbor, 'local-as', local_asn])

        # check validate() - local-as allowed only for ebgp peers
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['neighbor', neighbor, 'remote-as', remote_asn])

        self.cli_commit()

        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' neighbor {neighbor} remote-as {remote_asn}', frrconfig)
        self.assertIn(f' neighbor {neighbor} local-as {local_asn}', frrconfig)

    def test_bgp_16_import_rd_rt_compatibility(self):
        # Verify if import vrf and rd vpn export
        # exist in the same address family
        self.create_bgp_instances_for_import_test()
        self.cli_set(
            base_path + ['address-family', import_afi, 'import', 'vrf',
                         import_vrf])
        self.cli_set(
            base_path + ['address-family', import_afi, 'rd', 'vpn', 'export',
                         import_rd])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

    def test_bgp_17_import_rd_rt_compatibility(self):
        # Verify if vrf that is in import vrf list contains rd vpn export
        self.create_bgp_instances_for_import_test()
        self.cli_set(
            base_path + ['address-family', import_afi, 'import', 'vrf',
                         import_vrf])
        self.cli_commit()
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        frrconfig_vrf = self.getFRRconfig(f'router bgp {ASN} vrf {import_vrf}')

        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f'address-family ipv4 unicast', frrconfig)
        self.assertIn(f'  import vrf {import_vrf}', frrconfig)
        self.assertIn(f'router bgp {ASN} vrf {import_vrf}', frrconfig_vrf)

        self.cli_set(
            import_vrf_base + [import_vrf] + base_path + ['address-family',
                                                          import_afi, 'rd',
                                                          'vpn', 'export',
                                                          import_rd])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

    def test_bgp_18_deleting_import_vrf(self):
        # Verify deleting vrf that is in import vrf list
        self.create_bgp_instances_for_import_test()
        self.cli_set(
            base_path + ['address-family', import_afi, 'import', 'vrf',
                         import_vrf])
        self.cli_commit()
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        frrconfig_vrf = self.getFRRconfig(f'router bgp {ASN} vrf {import_vrf}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f'address-family ipv4 unicast', frrconfig)
        self.assertIn(f'  import vrf {import_vrf}', frrconfig)
        self.assertIn(f'router bgp {ASN} vrf {import_vrf}', frrconfig_vrf)
        self.cli_delete(import_vrf_base + [import_vrf])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

    def test_bgp_19_deleting_default_vrf(self):
        # Verify deleting existent vrf default if other vrfs were created
        self.create_bgp_instances_for_import_test()
        self.cli_commit()
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        frrconfig_vrf = self.getFRRconfig(f'router bgp {ASN} vrf {import_vrf}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f'router bgp {ASN} vrf {import_vrf}', frrconfig_vrf)
        self.cli_delete(base_path)
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

    def test_bgp_20_import_rd_rt_compatibility(self):
        # Verify if vrf that has rd vpn export is in import vrf of other vrfs
        self.create_bgp_instances_for_import_test()
        self.cli_set(
            import_vrf_base + [import_vrf] + base_path + ['address-family',
                                                          import_afi, 'rd',
                                                          'vpn', 'export',
                                                          import_rd])
        self.cli_commit()
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        frrconfig_vrf = self.getFRRconfig(f'router bgp {ASN} vrf {import_vrf}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f'router bgp {ASN} vrf {import_vrf}', frrconfig_vrf)
        self.assertIn(f'address-family ipv4 unicast', frrconfig_vrf)
        self.assertIn(f'  rd vpn export {import_rd}', frrconfig_vrf)

        self.cli_set(
            base_path + ['address-family', import_afi, 'import', 'vrf',
                         import_vrf])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

    def test_bgp_21_import_unspecified_vrf(self):
        # Verify if vrf that is in import is unspecified
        self.create_bgp_instances_for_import_test()
        self.cli_set(
            base_path + ['address-family', import_afi, 'import', 'vrf',
                         'test'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

    def test_bgp_22_interface_mpls_forwarding(self):
        interfaces = Section.interfaces('ethernet', vlan=False)
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface, 'mpls', 'forwarding'])

        self.cli_commit()

        for interface in interfaces:
            frrconfig = self.getFRRconfig(f'interface {interface}')
            self.assertIn(f'interface {interface}', frrconfig)
            self.assertIn(f' mpls bgp forwarding', frrconfig)

    def test_bgp_23_vrf_interface_mpls_forwarding(self):
        self.create_bgp_instances_for_import_test()
        interfaces = Section.interfaces('ethernet', vlan=False)
        for interface in interfaces:
            self.cli_set(['interfaces', 'ethernet', interface, 'vrf', import_vrf])
            self.cli_set(import_vrf_base + [import_vrf] + base_path + ['interface', interface, 'mpls', 'forwarding'])

        self.cli_commit()

        for interface in interfaces:
            frrconfig = self.getFRRconfig(f'interface {interface}')
            self.assertIn(f'interface {interface}', frrconfig)
            self.assertIn(f' mpls bgp forwarding', frrconfig)
            self.cli_delete(['interfaces', 'ethernet', interface, 'vrf'])

    def test_bgp_24_srv6_sid(self):
        locator_name = 'VyOS_foo'
        sid = 'auto'
        nexthop_ipv4 = '192.0.0.1'
        nexthop_ipv6 = '2001:db8:100:200::2'

        self.cli_set(base_path + ['srv6', 'locator', locator_name])
        self.cli_set(base_path + ['sid', 'vpn', 'per-vrf', 'export', sid])
        self.cli_set(base_path + ['address-family', 'ipv4-unicast', 'sid', 'vpn', 'export', sid])
        # verify() - SID per VRF and SID per address-family are mutually exclusive!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['address-family', 'ipv4-unicast', 'sid'])
        self.cli_commit()

        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' segment-routing srv6', frrconfig)
        self.assertIn(f'  locator {locator_name}', frrconfig)
        self.assertIn(f' sid vpn per-vrf export {sid}', frrconfig)

        # Now test AFI SID
        self.cli_delete(base_path + ['sid'])
        self.cli_set(base_path + ['address-family', 'ipv4-unicast', 'sid', 'vpn', 'export', sid])
        self.cli_set(base_path + ['address-family', 'ipv4-unicast', 'nexthop', 'vpn', 'export', nexthop_ipv4])
        self.cli_set(base_path + ['address-family', 'ipv6-unicast', 'sid', 'vpn', 'export', sid])
        self.cli_set(base_path + ['address-family', 'ipv6-unicast', 'nexthop', 'vpn', 'export', nexthop_ipv6])

        self.cli_commit()

        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' segment-routing srv6', frrconfig)
        self.assertIn(f'  locator {locator_name}', frrconfig)

        afiv4_config = self.getFRRconfig(' address-family ipv4 unicast')
        self.assertIn(f' sid vpn export {sid}', afiv4_config)
        self.assertIn(f' nexthop vpn export {nexthop_ipv4}', afiv4_config)
        afiv6_config = self.getFRRconfig(' address-family ipv6 unicast')
        self.assertIn(f' sid vpn export {sid}', afiv6_config)
        self.assertIn(f' nexthop vpn export {nexthop_ipv6}', afiv4_config)

    def test_bgp_25_ipv4_labeled_unicast_peer_group(self):
        pg_ipv4 = 'foo4'
        ipv4_max_prefix = '20'
        ipv4_prefix = '192.0.2.0/24'

        self.cli_set(base_path + ['listen', 'range', ipv4_prefix, 'peer-group', pg_ipv4])
        self.cli_set(base_path + ['parameters', 'labeled-unicast', 'ipv4-explicit-null'])
        self.cli_set(base_path + ['peer-group', pg_ipv4, 'address-family', 'ipv4-labeled-unicast', 'maximum-prefix', ipv4_max_prefix])
        self.cli_set(base_path + ['peer-group', pg_ipv4, 'remote-as', 'external'])

        self.cli_commit()

        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' neighbor {pg_ipv4} peer-group', frrconfig)
        self.assertIn(f' neighbor {pg_ipv4} remote-as external', frrconfig)
        self.assertIn(f' bgp listen range {ipv4_prefix} peer-group {pg_ipv4}', frrconfig)
        self.assertIn(f' bgp labeled-unicast ipv4-explicit-null', frrconfig)

        afiv4_config = self.getFRRconfig(' address-family ipv4 labeled-unicast')
        self.assertIn(f'  neighbor {pg_ipv4} activate', afiv4_config)
        self.assertIn(f'  neighbor {pg_ipv4} maximum-prefix {ipv4_max_prefix}', afiv4_config)

    def test_bgp_26_ipv6_labeled_unicast_peer_group(self):
        pg_ipv6 = 'foo6'
        ipv6_max_prefix = '200'
        ipv6_prefix = '2001:db8:1000::/64'

        self.cli_set(base_path + ['listen', 'range', ipv6_prefix, 'peer-group', pg_ipv6])
        self.cli_set(base_path + ['parameters', 'labeled-unicast', 'ipv6-explicit-null'])

        self.cli_set(base_path + ['peer-group', pg_ipv6, 'address-family', 'ipv6-labeled-unicast', 'maximum-prefix', ipv6_max_prefix])
        self.cli_set(base_path + ['peer-group', pg_ipv6, 'remote-as', 'external'])

        self.cli_commit()

        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' neighbor {pg_ipv6} peer-group', frrconfig)
        self.assertIn(f' neighbor {pg_ipv6} remote-as external', frrconfig)
        self.assertIn(f' bgp listen range {ipv6_prefix} peer-group {pg_ipv6}', frrconfig)
        self.assertIn(f' bgp labeled-unicast ipv6-explicit-null', frrconfig)

        afiv6_config = self.getFRRconfig(' address-family ipv6 labeled-unicast')
        self.assertIn(f'  neighbor {pg_ipv6} activate', afiv6_config)
        self.assertIn(f'  neighbor {pg_ipv6} maximum-prefix {ipv6_max_prefix}', afiv6_config)

    def test_bgp_27_route_reflector_client(self):
        self.cli_set(base_path + ['peer-group', 'peer1', 'address-family', 'l2vpn-evpn', 'route-reflector-client'])
        with self.assertRaises(ConfigSessionError) as e:
            self.cli_commit()

        self.cli_set(base_path + ['peer-group', 'peer1', 'remote-as', 'internal'])
        self.cli_commit()

        conf = self.getFRRconfig(' address-family l2vpn evpn')

        self.assertIn('neighbor peer1 route-reflector-client', conf)

    def test_bgp_28_peer_group_member_all_internal_or_external(self):
        def _common_config_check(conf, include_ras=True):
            if include_ras:
                self.assertIn(f'neighbor {int_neighbors[0]} remote-as {ASN}', conf)
                self.assertIn(f'neighbor {int_neighbors[1]} remote-as {ASN}', conf)
                self.assertIn(f'neighbor {ext_neighbors[0]} remote-as {int(ASN) + 1}',conf)

            self.assertIn(f'neighbor {int_neighbors[0]} peer-group {int_pg_name}', conf)
            self.assertIn(f'neighbor {int_neighbors[1]} peer-group {int_pg_name}', conf)
            self.assertIn(f'neighbor {ext_neighbors[0]} peer-group {ext_pg_name}', conf)

        int_neighbors = ['192.0.2.2', '192.0.2.3']
        ext_neighbors = ['192.122.2.2', '192.122.2.3']
        int_pg_name, ext_pg_name = 'SMOKETESTINT', 'SMOKETESTEXT'

        self.cli_set(base_path + ['neighbor', int_neighbors[0], 'peer-group', int_pg_name])
        self.cli_set(base_path + ['neighbor', int_neighbors[0], 'remote-as', ASN])
        self.cli_set(base_path + ['peer-group', int_pg_name, 'address-family', 'ipv4-unicast'])
        self.cli_set(base_path + ['neighbor', ext_neighbors[0], 'peer-group', ext_pg_name])
        self.cli_set(base_path + ['neighbor', ext_neighbors[0], 'remote-as', f'{int(ASN) + 1}'])
        self.cli_set(base_path + ['peer-group', ext_pg_name, 'address-family', 'ipv4-unicast'])
        self.cli_commit()

        # test add external remote-as to internal group
        self.cli_set(base_path + ['neighbor', int_neighbors[1], 'peer-group', int_pg_name])
        self.cli_set(base_path + ['neighbor', int_neighbors[1], 'remote-as', f'{int(ASN) + 1}'])

        with self.assertRaises(ConfigSessionError) as e:
            self.cli_commit()
        # self.assertIn('\nPeer-group members must be all internal or all external\n', str(e.exception))

        # test add internal remote-as to internal group
        self.cli_set(base_path + ['neighbor', int_neighbors[1], 'remote-as', ASN])
        self.cli_commit()

        conf = self.getFRRconfig(f'router bgp {ASN}')
        _common_config_check(conf)

        # test add internal remote-as to external group
        self.cli_set(base_path + ['neighbor', ext_neighbors[1], 'peer-group', ext_pg_name])
        self.cli_set(base_path + ['neighbor', ext_neighbors[1], 'remote-as', ASN])

        with self.assertRaises(ConfigSessionError) as e:
            self.cli_commit()
        # self.assertIn('\nPeer-group members must be all internal or all external\n', str(e.exception))

        # test add external remote-as to external group
        self.cli_set(base_path + ['neighbor', ext_neighbors[1], 'remote-as', f'{int(ASN) + 2}'])
        self.cli_commit()

        conf = self.getFRRconfig(f'router bgp {ASN}')
        _common_config_check(conf)
        self.assertIn(f'neighbor {ext_neighbors[1]} remote-as {int(ASN) + 2}', conf)
        self.assertIn(f'neighbor {ext_neighbors[1]} peer-group {ext_pg_name}', conf)

        # test named remote-as
        self.cli_set(base_path + ['neighbor', int_neighbors[0], 'remote-as', 'internal'])
        self.cli_set(base_path + ['neighbor', int_neighbors[1], 'remote-as', 'internal'])
        self.cli_set(base_path + ['neighbor', ext_neighbors[0], 'remote-as', 'external'])
        self.cli_set(base_path + ['neighbor', ext_neighbors[1], 'remote-as', 'external'])
        self.cli_commit()

        conf = self.getFRRconfig(f'router bgp {ASN}')
        _common_config_check(conf, include_ras=False)

        self.assertIn(f'neighbor {int_neighbors[0]} remote-as internal', conf)
        self.assertIn(f'neighbor {int_neighbors[1]} remote-as internal', conf)
        self.assertIn(f'neighbor {ext_neighbors[0]} remote-as external', conf)
        self.assertIn(f'neighbor {ext_neighbors[1]} remote-as external', conf)
        self.assertIn(f'neighbor {ext_neighbors[1]} peer-group {ext_pg_name}', conf)

    def test_bgp_29_peer_group_remote_as_equal_local_as(self):
        self.cli_set(base_path + ['system-as', ASN])
        self.cli_set(base_path + ['peer-group', 'OVERLAY', 'local-as', f'{int(ASN) + 1}'])
        self.cli_set(base_path + ['peer-group', 'OVERLAY', 'remote-as', f'{int(ASN) + 1}'])
        self.cli_set(base_path + ['peer-group', 'OVERLAY', 'address-family', 'l2vpn-evpn'])

        self.cli_set(base_path + ['peer-group', 'UNDERLAY', 'address-family', 'ipv4-unicast'])

        self.cli_set(base_path + ['neighbor', '10.177.70.62', 'peer-group', 'UNDERLAY'])
        self.cli_set(base_path + ['neighbor', '10.177.70.62', 'remote-as', 'external'])

        self.cli_set(base_path + ['neighbor', '10.177.75.1', 'peer-group', 'OVERLAY'])
        self.cli_set(base_path + ['neighbor', '10.177.75.2', 'peer-group', 'OVERLAY'])

        self.cli_commit()

        conf = self.getFRRconfig(f'router bgp {ASN}')

        self.assertIn(f'neighbor OVERLAY remote-as {int(ASN) + 1}', conf)
        self.assertIn(f'neighbor OVERLAY local-as {int(ASN) + 1}', conf)

    def test_bgp_99_bmp(self):
        target_name = 'instance-bmp'
        target_address = '127.0.0.1'
        target_port = '5000'
        min_retry = '1024'
        max_retry = '2048'
        monitor_ipv4 = 'pre-policy'
        monitor_ipv6 = 'pre-policy'
        mirror_buffer = '32000000'
        bmp_path = base_path + ['bmp']
        target_path = bmp_path + ['target', target_name]

        # by default the 'bmp' module not loaded for the bgpd expect Error
        self.cli_set(bmp_path)
        if not process_named_running('bgpd', 'bmp'):
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()

        # add required 'bmp' module to bgpd and restart bgpd
        self.cli_delete(bmp_path)
        self.cli_set(['system', 'frr', 'bmp'])
        self.cli_commit()

        # restart bgpd to apply "-M bmp" and update PID
        cmd(f'sudo kill -9 {self.daemon_pid}')
        # let the bgpd process recover
        sleep(10)
        # update daemon PID - this was a planned daemon restart
        self.daemon_pid = process_named_running(PROCESS_NAME)

        # set bmp config but not set address
        self.cli_set(target_path + ['port', target_port])
        # address is not set, expect Error
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # config other bmp options
        self.cli_set(target_path + ['address', target_address])
        self.cli_set(bmp_path + ['mirror-buffer-limit', mirror_buffer])
        self.cli_set(target_path + ['port', target_port])
        self.cli_set(target_path + ['min-retry', min_retry])
        self.cli_set(target_path + ['max-retry', max_retry])
        self.cli_set(target_path + ['mirror'])
        self.cli_set(target_path + ['monitor', 'ipv4-unicast', monitor_ipv4])
        self.cli_set(target_path + ['monitor', 'ipv6-unicast', monitor_ipv6])
        self.cli_commit()

        # Verify bgpd bmp configuration
        frrconfig = self.getFRRconfig(f'router bgp {ASN}')
        self.assertIn(f'bmp mirror buffer-limit {mirror_buffer}', frrconfig)
        self.assertIn(f'bmp targets {target_name}', frrconfig)
        self.assertIn(f'bmp mirror', frrconfig)
        self.assertIn(f'bmp monitor ipv4 unicast {monitor_ipv4}', frrconfig)
        self.assertIn(f'bmp monitor ipv6 unicast {monitor_ipv6}', frrconfig)
        self.assertIn(f'bmp connect {target_address} port {target_port} min-retry {min_retry} max-retry {max_retry}', frrconfig)

if __name__ == '__main__':
    unittest.main(verbosity=2)
