#!/usr/bin/env python3
#
# Copyright (C) 2020-2021 VyOS maintainers and contributors
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
import json

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import cmd

from base_interfaces_test import BasicInterfaceTest

remote_ip4 = '192.0.2.100'
remote_ip6 = '2001:db8::ffff'
source_if = 'dum2222'
mtu = 1476

def tunnel_conf(interface):
    tmp = cmd(f'ip -d -j link show {interface}')
    # {'address': '2.2.2.2',
    #  'broadcast': '192.0.2.10',
    #  'flags': ['POINTOPOINT', 'NOARP', 'UP', 'LOWER_UP'],
    #  'group': 'default',
    #  'gso_max_segs': 65535,
    #  'gso_max_size': 65536,
    #  'ifindex': 10,
    #  'ifname': 'tun10',
    #  'inet6_addr_gen_mode': 'none',
    #  'link': None,
    #  'link_pointtopoint': True,
    #  'link_type': 'gre',
    #  'linkinfo': {'info_data': {'local': '2.2.2.2',
    #                             'pmtudisc': True,
    #                             'remote': '192.0.2.10',
    #                             'tos': '0x1',
    #                             'ttl': 255},
    #               'info_kind': 'gre'},
    #  'linkmode': 'DEFAULT',
    #  'max_mtu': 65511,
    #  'min_mtu': 68,
    #  'mtu': 1476,
    #  'num_rx_queues': 1,
    #  'num_tx_queues': 1,
    #  'operstate': 'UNKNOWN',
    #  'promiscuity': 0,
    #  'qdisc': 'noqueue',
    #  'txqlen': 1000}
    return json.loads(tmp)[0]

class TunnelInterfaceTest(BasicInterfaceTest.BaseTest):
    @classmethod
    def setUpClass(cls):
        cls._test_ip = True
        cls._test_ipv6 = True
        cls._test_mtu = True
        cls._base_path = ['interfaces', 'tunnel']
        cls.local_v4 = '192.0.2.1'
        cls.local_v6 = '2001:db8::1'
        cls._options = {
            'tun10': ['encapsulation ipip', 'remote-ip 192.0.2.10', 'local-ip ' + cls.local_v4],
            'tun20': ['encapsulation gre',  'remote-ip 192.0.2.20', 'local-ip ' + cls.local_v4],
        }
        cls._interfaces = list(cls._options)

    def setUp(self):
        super().setUp()
        self.session.set(['interfaces', 'dummy', source_if, 'address', self.local_v4 + '/32'])
        self.session.set(['interfaces', 'dummy', source_if, 'address', self.local_v6 + '/128'])

    def tearDown(self):
        self.session.delete(['interfaces', 'dummy', source_if])
        super().tearDown()


    def test_ipv4_encapsulations(self):
        # When running tests ensure that for certain encapsulation types the
        # local and remote IP address is actually an IPv4 address

        interface = f'tun1000'
        local_if_addr = f'10.10.200.1/24'
        for encapsulation in ['ipip', 'sit', 'gre', 'gre-bridge']:
            self.session.set(self._base_path + [interface, 'address', local_if_addr])
            self.session.set(self._base_path + [interface, 'encapsulation', encapsulation])
            self.session.set(self._base_path + [interface, 'local-ip', self.local_v6])
            self.session.set(self._base_path + [interface, 'remote-ip', remote_ip6])

            # Encapsulation mode requires IPv4 local-ip
            with self.assertRaises(ConfigSessionError):
                self.session.commit()
            self.session.set(self._base_path + [interface, 'local-ip', self.local_v4])

            # Encapsulation mode requires IPv4 local-ip
            with self.assertRaises(ConfigSessionError):
                self.session.commit()
            self.session.set(self._base_path + [interface, 'remote-ip', remote_ip4])

            self.session.set(self._base_path + [interface, 'source-interface', source_if])

            # Source interface can not be used with sit and gre-bridge
            if encapsulation in ['sit', 'gre-bridge']:
                with self.assertRaises(ConfigSessionError):
                    self.session.commit()
                self.session.delete(self._base_path + [interface, 'source-interface'])

            # Check if commit is ok
            self.session.commit()

            conf = tunnel_conf(interface)
            self.assertEqual(interface, conf['ifname'])
            self.assertEqual(mtu, conf['mtu'])

            if encapsulation not in ['sit', 'gre-bridge']:
                self.assertEqual(source_if, conf['link'])
                self.assertEqual(encapsulation, conf['link_type'])
            elif encapsulation in ['gre-bridge']:
                self.assertEqual('ether', conf['link_type'])

            self.assertEqual(self.local_v4, conf['linkinfo']['info_data']['local'])
            self.assertEqual(remote_ip4,     conf['linkinfo']['info_data']['remote'])

            # cleanup this instance
            self.session.delete(self._base_path + [interface])
            self.session.commit()

    def test_ipv6_encapsulations(self):
        # When running tests ensure that for certain encapsulation types the
        # local and remote IP address is actually an IPv6 address

        interface = f'tun1010'
        local_if_addr = f'10.10.200.1/24'
        for encapsulation in ['ipip6', 'ip6ip6', 'ip6gre']:
            self.session.set(self._base_path + [interface, 'address', local_if_addr])
            self.session.set(self._base_path + [interface, 'encapsulation', encapsulation])
            self.session.set(self._base_path + [interface, 'local-ip', self.local_v4])
            self.session.set(self._base_path + [interface, 'remote-ip', remote_ip4])

            # Encapsulation mode requires IPv6 local-ip
            with self.assertRaises(ConfigSessionError):
                self.session.commit()
            self.session.set(self._base_path + [interface, 'local-ip', self.local_v6])

            # Encapsulation mode requires IPv6 local-ip
            with self.assertRaises(ConfigSessionError):
                self.session.commit()
            self.session.set(self._base_path + [interface, 'remote-ip', remote_ip6])

            # Configure Tunnel Source interface
            self.session.set(self._base_path + [interface, 'source-interface', source_if])

            # Check if commit is ok
            self.session.commit()

            conf = tunnel_conf(interface)
            self.assertEqual(interface, conf['ifname'])
            self.assertEqual(mtu, conf['mtu'])
            self.assertEqual(source_if, conf['link'])

            # remap encapsulation protocol(s)
            if encapsulation in ['ipip6', 'ip6ip6']:
                encapsulation = 'tunnel6'
            elif encapsulation in ['ip6gre']:
                encapsulation = 'gre6'

            self.assertEqual(encapsulation, conf['link_type'])

            self.assertEqual(self.local_v6, conf['linkinfo']['info_data']['local'])
            self.assertEqual(remote_ip6,     conf['linkinfo']['info_data']['remote'])

            # cleanup this instance
            self.session.delete(self._base_path + [interface])
            self.session.commit()

    def test_tunnel_verify_local_dhcp(self):
        # We can not use local-ip and dhcp-interface at the same time

        interface = f'tun1020'
        local_if_addr = f'10.0.0.1/24'

        self.session.set(self._base_path + [interface, 'address', local_if_addr])
        self.session.set(self._base_path + [interface, 'encapsulation', 'gre'])
        self.session.set(self._base_path + [interface, 'local-ip', self.local_v4])
        self.session.set(self._base_path + [interface, 'remote-ip', remote_ip4])
        self.session.set(self._base_path + [interface, 'dhcp-interface', 'eth0'])

        # local-ip and dhcp-interface can not be used at the same time
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(self._base_path + [interface, 'dhcp-interface'])

        # Check if commit is ok
        self.session.commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
