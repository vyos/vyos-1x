#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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
    def setUp(self):
        super().setUp()

        self._base_path = ['interfaces', 'tunnel']
        self._test_ip = False
        self._test_mtu = False

        self.local_v4 = '192.0.2.1'
        self.local_v6 = '2001:db8::1'

        self.session.set(['interfaces', 'dummy', source_if, 'address', self.local_v4 + '/32'])
        self.session.set(['interfaces', 'dummy', source_if, 'address', self.local_v6 + '/128'])

        self._options = {
            'tun10': ['encapsulation ipip', 'remote-ip 192.0.2.10', 'local-ip ' + self.local_v4],
            'tun20': ['encapsulation gre',  'remote-ip 192.0.2.20', 'local-ip ' + self.local_v4],
        }

        self._interfaces = list(self._options)

    def tearDown(self):
        self.session.delete(['interfaces', 'dummy', source_if])
        super().tearDown()

    def test_ipip(self):
        interface = 'tun100'
        encapsulation = 'ipip'
        local_if_addr = '10.10.10.1/24'

        self.session.set(self._base_path + [interface, 'address', local_if_addr])

        # Must provide an "encapsulation" for tunnel  tun10
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [interface, 'encapsulation', encapsulation])

        # Must configure either local-ip or dhcp-interface for tunnel ipip tun100
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [interface, 'local-ip', self.local_v4])

        # missing required option remote for ipip
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [interface, 'remote-ip', remote_ip4])

        # Configure Tunnel Source interface
        self.session.set(self._base_path + [interface, 'source-interface', source_if])

        self.session.commit()

        conf = tunnel_conf(interface)
        self.assertEqual(interface, conf['ifname'])
        self.assertEqual(encapsulation, conf['link_type'])
        self.assertEqual(1476, conf['mtu'])
        self.assertEqual(source_if, conf['link'])

        self.assertEqual(self.local_v4, conf['linkinfo']['info_data']['local'])
        self.assertEqual(remote_ip4,     conf['linkinfo']['info_data']['remote'])

    def test_ipip6(self):
        interface = 'tun110'
        encapsulation = 'ipip6'
        local_if_addr = '10.10.10.1/24'

        self.session.set(self._base_path + [interface, 'address', local_if_addr])

        # Must provide an "encapsulation" for tunnel  tun10
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [interface, 'encapsulation', encapsulation])

        # Must configure either local-ip or dhcp-interface for tunnel ipip tun100
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [interface, 'local-ip', self.local_v6])

        # missing required option remote for ipip
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [interface, 'remote-ip', remote_ip6])

        # Configure Tunnel Source interface
        self.session.set(self._base_path + [interface, 'source-interface', source_if])

        self.session.commit()

        conf = tunnel_conf(interface)
        self.assertEqual(interface, conf['ifname'])
        self.assertEqual('tunnel6', conf['link_type'])
        self.assertEqual(1476, conf['mtu'])
        self.assertEqual(source_if, conf['link'])

        self.assertEqual(self.local_v6, conf['linkinfo']['info_data']['local'])
        self.assertEqual(remote_ip6,     conf['linkinfo']['info_data']['remote'])

    def test_ip6ip6(self):
        interface = 'tun120'
        encapsulation = 'ip6ip6'
        local_if_addr = '2001:db8:f00::1/24'

        self.session.set(self._base_path + [interface, 'address', local_if_addr])

        # Must provide an "encapsulation" for tunnel  tun10
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [interface, 'encapsulation', encapsulation])

        # Must configure either local-ip or dhcp-interface for tunnel ipip tun100
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [interface, 'local-ip', self.local_v6])

        # missing required option remote for ipip
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [interface, 'remote-ip', remote_ip6])

        # Configure Tunnel Source interface
        self.session.set(self._base_path + [interface, 'source-interface', source_if])

        self.session.commit()

        conf = tunnel_conf(interface)
        self.assertEqual(interface, conf['ifname'])
        self.assertEqual('tunnel6', conf['link_type'])
        self.assertEqual(1476, conf['mtu'])
        self.assertEqual(source_if, conf['link'])

        self.assertEqual(self.local_v6, conf['linkinfo']['info_data']['local'])
        self.assertEqual(remote_ip6,     conf['linkinfo']['info_data']['remote'])

    def test_gre_ipv4(self):
        interface = 'tun200'
        encapsulation = 'gre'
        local_if_addr = '172.16.1.1/24'

        self.session.set(self._base_path + [interface, 'address', local_if_addr])

        # Must provide an "encapsulation" for tunnel  tun10
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [interface, 'encapsulation', encapsulation])

        # Must configure either local-ip or dhcp-interface
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [interface, 'local-ip', self.local_v4])

        # No assertion is raised for GRE remote-ip when missing
        self.session.set(self._base_path + [interface, 'remote-ip', remote_ip4])

        # Configure Tunnel Source interface
        self.session.set(self._base_path + [interface, 'source-interface', source_if])

        self.session.commit()

        conf = tunnel_conf(interface)
        self.assertEqual(interface, conf['ifname'])
        self.assertEqual(encapsulation, conf['link_type'])
        self.assertEqual(1476, conf['mtu'])
        self.assertEqual(source_if, conf['link'])

        self.assertEqual(self.local_v4, conf['linkinfo']['info_data']['local'])
        self.assertEqual(remote_ip4,     conf['linkinfo']['info_data']['remote'])


        def test_gre_ipv6(self):
            interface = 'tun210'
            encapsulation = 'ip6gre'
            local_if_addr = '2001:db8:f01::1/24'

            self.session.set(self._base_path + [interface, 'address', local_if_addr])

            # Must provide an "encapsulation" for tunnel  tun10
            with self.assertRaises(ConfigSessionError):
                self.session.commit()
            self.session.set(self._base_path + [interface, 'encapsulation', encapsulation])

            # Must configure either local-ip or dhcp-interface
            with self.assertRaises(ConfigSessionError):
                self.session.commit()
            self.session.set(self._base_path + [interface, 'local-ip', self.local_v6])

            # No assertion is raised for GRE remote-ip when missing
            self.session.set(self._base_path + [interface, 'remote-ip', remote_ip6])

            # Configure Tunnel Source interface
            self.session.set(self._base_path + [interface, 'source-interface', source_if])

            self.session.commit()

            conf = tunnel_conf(interface)
            self.assertEqual(interface, conf['ifname'])
            self.assertEqual(encapsulation, conf['link_type'])
            self.assertEqual(1476, conf['mtu'])
            self.assertEqual(source_if, conf['link'])

            self.assertEqual(self.local_v6, conf['linkinfo']['info_data']['local'])
            self.assertEqual(remote_ip6,     conf['linkinfo']['info_data']['remote'])


    def test_sit(self):
        interface = 'tun300'
        encapsulation = 'sit'
        local_if_addr = '172.16.2.1/24'

        self.session.set(self._base_path + [interface, 'address', local_if_addr])

        # Must provide an "encapsulation" for tunnel  tun10
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [interface, 'encapsulation', encapsulation])

        # Must configure either local-ip or dhcp-interface
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [interface, 'local-ip', self.local_v4])

        # No assertion is raised for GRE remote-ip when missing
        self.session.set(self._base_path + [interface, 'remote-ip', remote_ip4])

        # Source interface can not be used with si
        self.session.set(self._base_path + [interface, 'source-interface', source_if])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.delete(self._base_path + [interface, 'source-interface'])

        self.session.commit()

        conf = tunnel_conf(interface)
        self.assertEqual(interface, conf['ifname'])
        self.assertEqual(encapsulation, conf['link_type'])
        self.assertEqual(1476, conf['mtu'])

        self.assertEqual(self.local_v4, conf['linkinfo']['info_data']['local'])
        self.assertEqual(remote_ip4,     conf['linkinfo']['info_data']['remote'])


if __name__ == '__main__':
    unittest.main()
