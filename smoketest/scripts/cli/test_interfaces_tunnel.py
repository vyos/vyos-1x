#!/usr/bin/env python3
#
# Copyright (C) 2020-2022 VyOS maintainers and contributors
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

from base_interfaces_test import BasicInterfaceTest

from vyos.configsession import ConfigSessionError
from vyos.utils.network import get_interface_config
from vyos.template import inc_ip

remote_ip4 = '192.0.2.100'
remote_ip6 = '2001:db8::ffff'
source_if = 'dum2222'
mtu = 1476

class TunnelInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'tunnel']
        cls.local_v4 = '192.0.2.1'
        cls.local_v6 = '2001:db8::1'
        cls._options = {
            'tun10': ['encapsulation ipip', 'remote 192.0.2.10', 'source-address ' + cls.local_v4],
            'tun20': ['encapsulation gre',  'remote 192.0.2.20', 'source-address ' + cls.local_v4],
        }
        cls._interfaces = list(cls._options)
        # call base-classes classmethod
        super(TunnelInterfaceTest, cls).setUpClass()

        # create some test interfaces
        cls.cli_set(cls, ['interfaces', 'dummy', source_if, 'address', cls.local_v4 + '/32'])
        cls.cli_set(cls, ['interfaces', 'dummy', source_if, 'address', cls.local_v6 + '/128'])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['interfaces', 'dummy', source_if])
        super().tearDownClass()

    def test_ipv4_encapsulations(self):
        # When running tests ensure that for certain encapsulation types the
        # local and remote IP address is actually an IPv4 address

        interface = f'tun1000'
        local_if_addr = f'10.10.200.1/24'
        for encapsulation in ['ipip', 'sit', 'gre', 'gretap']:
            self.cli_set(self._base_path + [interface, 'address', local_if_addr])
            self.cli_set(self._base_path + [interface, 'encapsulation', encapsulation])
            self.cli_set(self._base_path + [interface, 'source-address', self.local_v6])
            self.cli_set(self._base_path + [interface, 'remote', remote_ip6])

            # Encapsulation mode requires IPv4 source-address
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_set(self._base_path + [interface, 'source-address', self.local_v4])

            # Encapsulation mode requires IPv4 remote
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_set(self._base_path + [interface, 'remote', remote_ip4])
            self.cli_set(self._base_path + [interface, 'source-interface', source_if])

            # Source interface can not be used with sit and gretap
            if encapsulation in ['sit', 'gretap']:
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
                self.cli_delete(self._base_path + [interface, 'source-interface'])

            # Check if commit is ok
            self.cli_commit()

            conf = get_interface_config(interface)
            if encapsulation not in ['sit', 'gretap']:
                self.assertEqual(source_if, conf['link'])

            self.assertEqual(interface, conf['ifname'])
            self.assertEqual(mtu, conf['mtu'])
            self.assertEqual(encapsulation, conf['linkinfo']['info_kind'])
            self.assertEqual(self.local_v4, conf['linkinfo']['info_data']['local'])
            self.assertEqual(remote_ip4,    conf['linkinfo']['info_data']['remote'])
            self.assertTrue(conf['linkinfo']['info_data']['pmtudisc'])

            # cleanup this instance
            self.cli_delete(self._base_path + [interface])
            self.cli_commit()

    def test_ipv6_encapsulations(self):
        # When running tests ensure that for certain encapsulation types the
        # local and remote IP address is actually an IPv6 address

        interface = f'tun1010'
        local_if_addr = f'10.10.200.1/24'
        for encapsulation in ['ipip6', 'ip6ip6', 'ip6gre', 'ip6gretap']:
            self.cli_set(self._base_path + [interface, 'address', local_if_addr])
            self.cli_set(self._base_path + [interface, 'encapsulation', encapsulation])
            self.cli_set(self._base_path + [interface, 'source-address', self.local_v4])
            self.cli_set(self._base_path + [interface, 'remote', remote_ip4])

            # Encapsulation mode requires IPv6 source-address
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_set(self._base_path + [interface, 'source-address', self.local_v6])

            # Encapsulation mode requires IPv6 remote
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_set(self._base_path + [interface, 'remote', remote_ip6])

            # Configure Tunnel Source interface
            self.cli_set(self._base_path + [interface, 'source-interface', source_if])
            # Source interface can not be used with ip6gretap
            if encapsulation in ['ip6gretap']:
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
                self.cli_delete(self._base_path + [interface, 'source-interface'])

            # Check if commit is ok
            self.cli_commit()

            conf = get_interface_config(interface)
            if encapsulation not in ['ip6gretap']:
                self.assertEqual(source_if, conf['link'])

            self.assertEqual(interface, conf['ifname'])
            self.assertEqual(mtu, conf['mtu'])

            # Not applicable for ip6gre
            if 'proto' in conf['linkinfo']['info_data']:
                self.assertEqual(encapsulation, conf['linkinfo']['info_data']['proto'])

            # remap encapsulation protocol(s) only for ipip6, ip6ip6
            if encapsulation in ['ipip6', 'ip6ip6']:
                encapsulation = 'ip6tnl'

            self.assertEqual(encapsulation, conf['linkinfo']['info_kind'])
            self.assertEqual(self.local_v6, conf['linkinfo']['info_data']['local'])
            self.assertEqual(remote_ip6,    conf['linkinfo']['info_data']['remote'])

            # cleanup this instance
            self.cli_delete(self._base_path + [interface])
            self.cli_commit()

    def test_tunnel_parameters_gre(self):
        interface = f'tun1030'
        gre_key = '10'
        encapsulation = 'gre'
        tos = '20'

        self.cli_set(self._base_path + [interface, 'encapsulation', encapsulation])
        self.cli_set(self._base_path + [interface, 'source-address', self.local_v4])
        self.cli_set(self._base_path + [interface, 'remote', remote_ip4])

        self.cli_set(self._base_path + [interface, 'parameters', 'ip', 'no-pmtu-discovery'])
        self.cli_set(self._base_path + [interface, 'parameters', 'ip', 'key', gre_key])
        self.cli_set(self._base_path + [interface, 'parameters', 'ip', 'tos', tos])
        self.cli_set(self._base_path + [interface, 'parameters', 'ip', 'ttl', '0'])

        # Check if commit is ok
        self.cli_commit()

        conf = get_interface_config(interface)
        self.assertEqual(mtu,           conf['mtu'])
        self.assertEqual(interface,     conf['ifname'])
        self.assertEqual(encapsulation, conf['linkinfo']['info_kind'])
        self.assertEqual(self.local_v4, conf['linkinfo']['info_data']['local'])
        self.assertEqual(remote_ip4,    conf['linkinfo']['info_data']['remote'])
        self.assertEqual(0,             conf['linkinfo']['info_data']['ttl'])
        self.assertFalse(               conf['linkinfo']['info_data']['pmtudisc'])

    def test_gretap_parameters_change(self):
        interface = f'tun1040'
        gre_key = '10'
        encapsulation = 'gretap'
        tos = '20'

        self.cli_set(self._base_path + [interface, 'encapsulation', encapsulation])
        self.cli_set(self._base_path + [interface, 'source-address', self.local_v4])
        self.cli_set(self._base_path + [interface, 'remote', remote_ip4])

        # Check if commit is ok
        self.cli_commit()

        conf = get_interface_config(interface)
        self.assertEqual(mtu,           conf['mtu'])
        self.assertEqual(interface,     conf['ifname'])
        self.assertEqual(encapsulation, conf['linkinfo']['info_kind'])
        self.assertEqual(self.local_v4, conf['linkinfo']['info_data']['local'])
        self.assertEqual(remote_ip4,    conf['linkinfo']['info_data']['remote'])
        self.assertEqual(64,            conf['linkinfo']['info_data']['ttl'])

        # Change remote ip address (inc host by 2
        new_remote = inc_ip(remote_ip4, 2)
        self.cli_set(self._base_path + [interface, 'remote', new_remote])
        # Check if commit is ok
        self.cli_commit()

        conf = get_interface_config(interface)
        self.assertEqual(new_remote,    conf['linkinfo']['info_data']['remote'])

    def test_erspan_v1(self):
        interface = f'tun1070'
        encapsulation = 'erspan'
        ip_key = '77'
        idx = '20'

        self.cli_set(self._base_path + [interface, 'encapsulation', encapsulation])
        self.cli_set(self._base_path + [interface, 'source-address', self.local_v4])
        self.cli_set(self._base_path + [interface, 'remote', remote_ip4])

        self.cli_set(self._base_path + [interface, 'parameters', 'erspan', 'index', idx])

        # ERSPAN requires ip key parameter
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(self._base_path + [interface, 'parameters', 'ip', 'key', ip_key])

        # Check if commit is ok
        self.cli_commit()

        conf = get_interface_config(interface)
        self.assertEqual(mtu,               conf['mtu'])
        self.assertEqual(interface,         conf['ifname'])
        self.assertEqual(encapsulation,     conf['linkinfo']['info_kind'])
        self.assertEqual(self.local_v4,     conf['linkinfo']['info_data']['local'])
        self.assertEqual(remote_ip4,        conf['linkinfo']['info_data']['remote'])
        self.assertEqual(64,                conf['linkinfo']['info_data']['ttl'])
        self.assertEqual(f'0.0.0.{ip_key}', conf['linkinfo']['info_data']['ikey'])
        self.assertEqual(f'0.0.0.{ip_key}', conf['linkinfo']['info_data']['okey'])
        self.assertEqual(int(idx),          conf['linkinfo']['info_data']['erspan_index'])
        # version defaults to 1
        self.assertEqual(1,                 conf['linkinfo']['info_data']['erspan_ver'])
        self.assertTrue(                    conf['linkinfo']['info_data']['iseq'])
        self.assertTrue(                    conf['linkinfo']['info_data']['oseq'])

        # Change remote ip address (inc host by 2
        new_remote = inc_ip(remote_ip4, 2)
        self.cli_set(self._base_path + [interface, 'remote', new_remote])
        # Check if commit is ok
        self.cli_commit()

        conf = get_interface_config(interface)
        self.assertEqual(new_remote,    conf['linkinfo']['info_data']['remote'])

    def test_ip6erspan_v2(self):
        interface = f'tun1070'
        encapsulation = 'ip6erspan'
        ip_key = '77'
        erspan_ver = 2
        direction = 'ingress'

        self.cli_set(self._base_path + [interface, 'encapsulation', encapsulation])
        self.cli_set(self._base_path + [interface, 'source-address', self.local_v6])
        self.cli_set(self._base_path + [interface, 'remote', remote_ip6])

        # ERSPAN requires ip key parameter
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(self._base_path + [interface, 'parameters', 'ip', 'key', ip_key])

        self.cli_set(self._base_path + [interface, 'parameters', 'erspan', 'version', str(erspan_ver)])

        # ERSPAN index is not valid on version 2
        self.cli_set(self._base_path + [interface, 'parameters', 'erspan', 'index', '10'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(self._base_path + [interface, 'parameters', 'erspan', 'index'])

        # ERSPAN requires direction to be set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(self._base_path + [interface, 'parameters', 'erspan', 'direction', direction])

        # Check if commit is ok
        self.cli_commit()

        conf = get_interface_config(interface)
        self.assertEqual(mtu,               conf['mtu'])
        self.assertEqual(interface,         conf['ifname'])
        self.assertEqual(encapsulation,     conf['linkinfo']['info_kind'])
        self.assertEqual(self.local_v6,     conf['linkinfo']['info_data']['local'])
        self.assertEqual(remote_ip6,        conf['linkinfo']['info_data']['remote'])
        self.assertEqual(64,                conf['linkinfo']['info_data']['ttl'])
        self.assertEqual(f'0.0.0.{ip_key}', conf['linkinfo']['info_data']['ikey'])
        self.assertEqual(f'0.0.0.{ip_key}', conf['linkinfo']['info_data']['okey'])
        self.assertEqual(erspan_ver,        conf['linkinfo']['info_data']['erspan_ver'])
        self.assertEqual(direction,         conf['linkinfo']['info_data']['erspan_dir'])
        self.assertTrue(                    conf['linkinfo']['info_data']['iseq'])
        self.assertTrue(                    conf['linkinfo']['info_data']['oseq'])

        # Change remote ip address (inc host by 2
        new_remote = inc_ip(remote_ip6, 2)
        self.cli_set(self._base_path + [interface, 'remote', new_remote])
        # Check if commit is ok
        self.cli_commit()

        conf = get_interface_config(interface)
        self.assertEqual(new_remote,    conf['linkinfo']['info_data']['remote'])

    def test_tunnel_src_any_gre_key(self):
        interface = f'tun1280'
        encapsulation = 'gre'
        src_addr = '0.0.0.0'
        key = '127'

        self.cli_set(self._base_path + [interface, 'encapsulation', encapsulation])
        self.cli_set(self._base_path + [interface, 'source-address', src_addr])
        # GRE key must be supplied with a 0.0.0.0 source address
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(self._base_path + [interface, 'parameters', 'ip', 'key', key])

        self.cli_commit()

    def test_multiple_gre_tunnel_same_remote(self):
        tunnels = {
            'tun10' : {
                'encapsulation' : 'gre',
                'source_interface' : source_if,
                'remote' : '1.2.3.4',
            },
            'tun20' : {
                'encapsulation' : 'gre',
                'source_interface' : source_if,
                'remote' : '1.2.3.4',
            },
        }

        for tunnel, tunnel_config in tunnels.items():
            self.cli_set(self._base_path + [tunnel, 'encapsulation', tunnel_config['encapsulation']])
            if 'source_interface' in tunnel_config:
                self.cli_set(self._base_path + [tunnel, 'source-interface', tunnel_config['source_interface']])
            if 'remote' in tunnel_config:
                self.cli_set(self._base_path + [tunnel, 'remote', tunnel_config['remote']])

        # GRE key must be supplied when two or more tunnels are formed to the same desitnation
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for tunnel, tunnel_config in tunnels.items():
            self.cli_set(self._base_path + [tunnel, 'parameters', 'ip', 'key', tunnel.lstrip('tun')])

        self.cli_commit()

        for tunnel, tunnel_config in tunnels.items():
            conf = get_interface_config(tunnel)
            ip_key = tunnel.lstrip('tun')

            self.assertEqual(tunnel_config['source_interface'], conf['link'])
            self.assertEqual(tunnel_config['encapsulation'],    conf['linkinfo']['info_kind'])
            self.assertEqual(tunnel_config['remote'],           conf['linkinfo']['info_data']['remote'])
            self.assertEqual(f'0.0.0.{ip_key}',                 conf['linkinfo']['info_data']['ikey'])
            self.assertEqual(f'0.0.0.{ip_key}',                 conf['linkinfo']['info_data']['okey'])

    def test_multiple_gre_tunnel_different_remote(self):
        tunnels = {
            'tun10' : {
                'encapsulation' : 'gre',
                'source_interface' : source_if,
                'remote' : '1.2.3.4',
            },
            'tun20' : {
                'encapsulation' : 'gre',
                'source_interface' : source_if,
                'remote' : '1.2.3.5',
            },
        }

        for tunnel, tunnel_config in tunnels.items():
            self.cli_set(self._base_path + [tunnel, 'encapsulation', tunnel_config['encapsulation']])
            if 'source_interface' in tunnel_config:
                self.cli_set(self._base_path + [tunnel, 'source-interface', tunnel_config['source_interface']])
            if 'remote' in tunnel_config:
                self.cli_set(self._base_path + [tunnel, 'remote', tunnel_config['remote']])

        self.cli_commit()

        for tunnel, tunnel_config in tunnels.items():
            conf = get_interface_config(tunnel)

            self.assertEqual(tunnel_config['source_interface'], conf['link'])
            self.assertEqual(tunnel_config['encapsulation'],    conf['linkinfo']['info_kind'])
            self.assertEqual(tunnel_config['remote'],           conf['linkinfo']['info_data']['remote'])

    def test_tunnel_invalid_source_interface(self):
        encapsulation = 'gre'
        remote = '192.0.2.1'
        interface = 'tun7543'

        self.cli_set(self._base_path + [interface, 'encapsulation', encapsulation])
        self.cli_set(self._base_path + [interface, 'remote', remote])

        for dynamic_interface in ['l2tp0', 'ppp4220', 'sstpc0', 'ipoe654']:
            self.cli_set(self._base_path + [interface, 'source-interface', dynamic_interface])
            # verify() - we can not source from dynamic interfaces
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
        self.cli_set(self._base_path + [interface, 'source-interface', 'eth0'])
        self.cli_commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
