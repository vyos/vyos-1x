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

mtu = 1500

def erspan_conf(interface):
    tmp = cmd(f'ip -d -j link show {interface}')
    '''
    [
        {
            "ifindex": 17,
            "link": null,
            "ifname": "ersp0",
            "flags": [
                "BROADCAST",
                "MULTICAST"
            ],
            "mtu": 1450,
            "qdisc": "noop",
            "operstate": "DOWN",
            "linkmode": "DEFAULT",
            "group": "default",
            "txqlen": 1000,
            "link_type": "ether",
            "address": "22:27:14:7b:0d:79",
            "broadcast": "ff:ff:ff:ff:ff:ff",
            "promiscuity": 0,
            "min_mtu": 68,
            "max_mtu": 0,
            "linkinfo": {
                "info_kind": "erspan",
                "info_data": {
                    "remote": "10.2.2.2",
                    "local": "10.1.1.1",
                    "ttl": 0,
                    "pmtudisc": true,
                    "ikey": "0.0.0.123",
                    "okey": "0.0.0.123",
                    "iseq": true,
                    "oseq": true,
                    "erspan_index": 0,
                    "erspan_ver": 1
                }
            },
            "inet6_addr_gen_mode": "eui64",
            "num_tx_queues": 1,
            "num_rx_queues": 1,
            "gso_max_size": 65536,
            "gso_max_segs": 65535
        }
    ]
    '''
    return json.loads(tmp)[0]

class ERSPanTunnelInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
        super().setUp()

        self._base_path = ['interfaces', 'erspan']
        self._test_mtu = True

        self.local_v4 = '10.1.1.1'
        self.local_v6 = '2001:db8::1'
        self.remote_v4 = '10.2.2.2'
        self.remote_v6 = '2001:db9::1'

    def tearDown(self):
        self.session.delete(['interfaces', 'erspan'])
        super().tearDown()

    def test_erspan_ipv4(self):
        interface = 'ersp100'
        encapsulation = 'erspan'
        key = 123

        self.session.set(self._base_path + [interface, 'encapsulation', encapsulation])
        self.session.set(self._base_path + [interface, 'local-ip', self.local_v4])
        self.session.set(self._base_path + [interface, 'remote-ip', self.remote_v4])
        self.session.set(self._base_path + [interface, 'parameters', 'ip' , 'key', str(key)])

        self.session.commit()

        conf = erspan_conf(interface)
        self.assertEqual(interface, conf['ifname'])
        self.assertEqual(encapsulation, conf['linkinfo']['info_kind'])
        self.assertEqual(mtu, conf['mtu'])

        self.assertEqual(self.local_v4, conf['linkinfo']['info_data']['local'])
        self.assertEqual(self.remote_v4,     conf['linkinfo']['info_data']['remote'])


    def test_erspan_ipv6(self):
        interface = 'ersp1000'
        encapsulation = 'ip6erspan'
        key = 123

        self.session.set(self._base_path + [interface, 'encapsulation', encapsulation])
        self.session.set(self._base_path + [interface, 'local-ip', self.local_v6])
        self.session.set(self._base_path + [interface, 'remote-ip', self.remote_v6])
        self.session.set(self._base_path + [interface, 'parameters', 'ip' , 'key', str(key)])

        self.session.commit()

        conf = erspan_conf(interface)
        self.assertEqual(interface, conf['ifname'])
        self.assertEqual(encapsulation, conf['linkinfo']['info_kind'])
        self.assertEqual(mtu, conf['mtu'])

        self.assertEqual(self.local_v6, conf['linkinfo']['info_data']['local'])
        self.assertEqual(self.remote_v6,     conf['linkinfo']['info_data']['remote'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
