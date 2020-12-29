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

import os
import jmespath
import json
import unittest

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import cmd
from vyos.util import dict_search

base_path = ['nat']
src_path = base_path + ['source']
dst_path = base_path + ['destination']

class TestNAT(unittest.TestCase):
    def setUp(self):
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        self.session = ConfigSession(os.getpid())
        self.session.delete(base_path)

    def tearDown(self):
        self.session.delete(base_path)
        self.session.commit()

    def test_snat(self):
        """ Test source NAT (SNAT) rules """

        rules = ['100', '110', '120', '130', '200', '210', '220', '230']
        outbound_iface_100 = 'eth0'
        outbound_iface_200 = 'eth1'
        for rule in rules:
            network = f'192.168.{rule}.0/24'
            # depending of rule order we check either for source address for NAT
            # or configured destination address for NAT
            if int(rule) < 200:
                self.session.set(src_path + ['rule', rule, 'source', 'address', network])
                self.session.set(src_path + ['rule', rule, 'outbound-interface', outbound_iface_100])
                self.session.set(src_path + ['rule', rule, 'translation', 'address', 'masquerade'])
            else:
                self.session.set(src_path + ['rule', rule, 'destination', 'address', network])
                self.session.set(src_path + ['rule', rule, 'outbound-interface', outbound_iface_200])
                self.session.set(src_path + ['rule', rule, 'exclude'])

        self.session.commit()

        tmp = cmd('sudo nft -j list table nat')
        data_json = jmespath.search('nftables[?rule].rule[?chain]', json.loads(tmp))

        for idx in range(0, len(data_json)):
            rule = str(rules[idx])
            data = data_json[idx]
            network = f'192.168.{rule}.0/24'

            self.assertEqual(data['chain'], 'POSTROUTING')
            self.assertEqual(data['comment'], f'SRC-NAT-{rule}')
            self.assertEqual(data['family'], 'ip')
            self.assertEqual(data['table'], 'nat')

            iface = dict_search('match.right', data['expr'][0])
            direction = dict_search('match.left.payload.field', data['expr'][1])
            address = dict_search('match.right.prefix.addr', data['expr'][1])
            mask = dict_search('match.right.prefix.len', data['expr'][1])

            if int(rule) < 200:
                self.assertEqual(direction, 'saddr')
                self.assertEqual(iface, outbound_iface_100)
                # check for masquerade keyword
                self.assertIn('masquerade', data['expr'][3])
            else:
                self.assertEqual(direction, 'daddr')
                self.assertEqual(iface, outbound_iface_200)
                # check for return keyword due to 'exclude'
                self.assertIn('return', data['expr'][3])

            self.assertEqual(f'{address}/{mask}', network)

    def test_dnat(self):
        """ Test destination NAT (DNAT) rules """

        rules = ['100', '110', '120', '130', '200', '210', '220', '230']
        inbound_iface_100 = 'eth0'
        inbound_iface_200 = 'eth1'
        inbound_proto_100 = 'udp'
        inbound_proto_200 = 'tcp'

        for rule in rules:
            port = f'10{rule}'
            self.session.set(dst_path + ['rule', rule, 'source', 'port', port])
            self.session.set(dst_path + ['rule', rule, 'translation', 'address', '192.0.2.1'])
            self.session.set(dst_path + ['rule', rule, 'translation', 'port', port])
            if int(rule) < 200:
                self.session.set(dst_path + ['rule', rule, 'protocol', inbound_proto_100])
                self.session.set(dst_path + ['rule', rule, 'inbound-interface', inbound_iface_100])
            else:
                self.session.set(dst_path + ['rule', rule, 'protocol', inbound_proto_200])
                self.session.set(dst_path + ['rule', rule, 'inbound-interface', inbound_iface_200])

        self.session.commit()

        tmp = cmd('sudo nft -j list table nat')
        data_json = jmespath.search('nftables[?rule].rule[?chain]', json.loads(tmp))

        for idx in range(0, len(data_json)):
            rule = str(rules[idx])
            data = data_json[idx]
            port = int(f'10{rule}')

            self.assertEqual(data['chain'], 'PREROUTING')
            self.assertEqual(data['comment'].split()[0], f'DST-NAT-{rule}')
            self.assertEqual(data['family'], 'ip')
            self.assertEqual(data['table'], 'nat')

            iface = dict_search('match.right', data['expr'][0])
            direction = dict_search('match.left.payload.field', data['expr'][1])
            protocol = dict_search('match.left.payload.protocol', data['expr'][1])
            dnat_addr = dict_search('dnat.addr', data['expr'][3])
            dnat_port = dict_search('dnat.port', data['expr'][3])

            self.assertEqual(direction, 'sport')
            self.assertEqual(dnat_addr, '192.0.2.1')
            self.assertEqual(dnat_port, port)
            if int(rule) < 200:
                self.assertEqual(iface, inbound_iface_100)
                self.assertEqual(protocol, inbound_proto_100)
            else:
                self.assertEqual(iface, inbound_iface_200)


    def test_validation_logic(self):
        """ T2813: Ensure translation address is specified """
        rule = '5'
        self.session.set(src_path + ['rule', rule, 'source', 'address', '192.0.2.0/24'])

        # check validate() - outbound-interface must be defined
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(src_path + ['rule', rule, 'outbound-interface', 'eth0'])

        # check validate() - translation address not specified
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

        self.session.set(src_path + ['rule', rule, 'translation', 'address', 'masquerade'])
        self.session.commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
