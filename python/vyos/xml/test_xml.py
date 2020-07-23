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
#
#

import os
import unittest
from unittest import TestCase, mock

from vyos.xml import load_configuration

import sys


class TestSearch(TestCase):
    def setUp(self):
        self.xml = load_configuration()
 
    def test_(self):
        last = self.xml.traverse("")
        self.assertEqual(last, '')
        self.assertEqual(self.xml.inside, [])
        self.assertEqual(self.xml.options, ['firewall', 'high-availability', 'interfaces', 'nat', 'protocols', 'service', 'system', 'vpn', 'vrf'])
        self.assertEqual(self.xml.filling, False)
        self.assertEqual(self.xml.word, last)
        self.assertEqual(self.xml.check, False)
        self.assertEqual(self.xml.final, False)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, False)
        self.assertEqual(self.xml.plain, True)

    def test_i(self):
        last = self.xml.traverse("i")
        self.assertEqual(last, 'i')
        self.assertEqual(self.xml.inside, [])
        self.assertEqual(self.xml.options, ['interfaces'])
        self.assertEqual(self.xml.filling, True)
        self.assertEqual(self.xml.word, last)
        self.assertEqual(self.xml.check, False)
        self.assertEqual(self.xml.final, False)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, False)
        self.assertEqual(self.xml.plain, True)

    def test_interfaces(self):
        last = self.xml.traverse("interfaces")
        self.assertEqual(last, '')
        self.assertEqual(self.xml.inside, ['interfaces'])
        self.assertEqual(self.xml.options, ['bonding', 'bridge', 'dummy', 'ethernet', 'geneve', 'l2tpv3', 'loopback', 'macsec', 'openvpn', 'pppoe', 'pseudo-ethernet', 'tunnel', 'vxlan', 'wireguard', 'wireless', 'wirelessmodem'])
        self.assertEqual(self.xml.filling, False)
        self.assertEqual(self.xml.word, '')
        self.assertEqual(self.xml.check, False)
        self.assertEqual(self.xml.final, False)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, False)
        self.assertEqual(self.xml.plain, True)

    def test_interfaces_space(self):
        last = self.xml.traverse("interfaces ")
        self.assertEqual(last, '')
        self.assertEqual(self.xml.inside, ['interfaces'])
        self.assertEqual(self.xml.options, ['bonding', 'bridge', 'dummy', 'ethernet', 'geneve', 'l2tpv3', 'loopback', 'macsec', 'openvpn', 'pppoe', 'pseudo-ethernet', 'tunnel', 'vxlan', 'wireguard', 'wireless', 'wirelessmodem'])
        self.assertEqual(self.xml.filling, False)
        self.assertEqual(self.xml.word, last)
        self.assertEqual(self.xml.check, False)
        self.assertEqual(self.xml.final, False)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, False)
        self.assertEqual(self.xml.plain, True)

    def test_interfaces_w(self):
        last = self.xml.traverse("interfaces w")
        self.assertEqual(last, 'w')
        self.assertEqual(self.xml.inside, ['interfaces'])
        self.assertEqual(self.xml.options, ['wireguard', 'wireless', 'wirelessmodem'])
        self.assertEqual(self.xml.filling, True)
        self.assertEqual(self.xml.word, last)
        self.assertEqual(self.xml.check, True)
        self.assertEqual(self.xml.final, False)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, False)
        self.assertEqual(self.xml.plain, True)

    def test_interfaces_ethernet(self):
        last = self.xml.traverse("interfaces ethernet")
        self.assertEqual(last, '')
        self.assertEqual(self.xml.inside, ['interfaces', 'ethernet'])
        self.assertEqual(self.xml.options, [])
        self.assertEqual(self.xml.filling, False)
        self.assertEqual(self.xml.word, '')
        self.assertEqual(self.xml.check, False)
        self.assertEqual(self.xml.final, False)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, False)
        self.assertEqual(self.xml.plain, False)

    def test_interfaces_ethernet_space(self):
        last = self.xml.traverse("interfaces ethernet ")
        self.assertEqual(last, '')
        self.assertEqual(self.xml.inside, ['interfaces', 'ethernet'])
        self.assertEqual(self.xml.options, [])
        self.assertEqual(self.xml.filling, False)
        self.assertEqual(self.xml.word, '')
        self.assertEqual(self.xml.check, False)
        self.assertEqual(self.xml.final, False)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, False)
        self.assertEqual(self.xml.plain, False)

    def test_interfaces_ethernet_e(self):
        last = self.xml.traverse("interfaces ethernet e")
        self.assertEqual(last, 'e')
        self.assertEqual(self.xml.inside, ['interfaces', 'ethernet'])
        self.assertEqual(self.xml.options, [])
        self.assertEqual(self.xml.filling, True)
        self.assertEqual(self.xml.word, last)
        self.assertEqual(self.xml.check, True)
        self.assertEqual(self.xml.final, False)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, False)
        self.assertEqual(self.xml.plain, False)

    def test_interfaces_la(self):
        last = self.xml.traverse("interfaces ethernet la")
        self.assertEqual(last, 'la')
        self.assertEqual(self.xml.inside, ['interfaces', 'ethernet'])
        self.assertEqual(self.xml.options, [])
        self.assertEqual(self.xml.filling, True)
        self.assertEqual(self.xml.word, last)
        self.assertEqual(self.xml.check, True)
        self.assertEqual(self.xml.final, False)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, False)
        self.assertEqual(self.xml.plain, False)

    def test_interfaces_ethernet_lan0(self):
        last = self.xml.traverse("interfaces ethernet lan0")
        self.assertEqual(last, 'lan0')
        self.assertEqual(self.xml.inside, ['interfaces', 'ethernet'])
        self.assertEqual(self.xml.options, [])
        self.assertEqual(self.xml.filling, True)
        self.assertEqual(self.xml.word, last)
        self.assertEqual(self.xml.check, True)
        self.assertEqual(self.xml.final, False)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, False)
        self.assertEqual(self.xml.plain, False)

    def test_interfaces_ethernet_lan0_space(self):
        last = self.xml.traverse("interfaces ethernet lan0 ")
        self.assertEqual(last, '')
        self.assertEqual(self.xml.inside, ['interfaces', 'ethernet'])
        self.assertEqual(len(self.xml.options), 19)
        self.assertEqual(self.xml.filling, False)
        self.assertEqual(self.xml.word, last)
        self.assertEqual(self.xml.check, False)
        self.assertEqual(self.xml.final, False)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, True)
        self.assertEqual(self.xml.plain, False)

    def test_interfaces_ethernet_lan0_ad(self):
        last = self.xml.traverse("interfaces ethernet lan0 ad")
        self.assertEqual(last, 'ad')
        self.assertEqual(self.xml.inside, ['interfaces', 'ethernet'])
        self.assertEqual(self.xml.options, ['address'])
        self.assertEqual(self.xml.filling, True)
        self.assertEqual(self.xml.word, last)
        self.assertEqual(self.xml.check, False)
        self.assertEqual(self.xml.final, False)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, False)
        self.assertEqual(self.xml.plain, False)

    def test_interfaces_ethernet_lan0_address(self):
        last = self.xml.traverse("interfaces ethernet lan0 address")
        self.assertEqual(last, '')
        self.assertEqual(self.xml.inside, ['interfaces', 'ethernet', 'address'])
        self.assertEqual(self.xml.options, [])
        self.assertEqual(self.xml.filling, False)
        self.assertEqual(self.xml.word, last)
        self.assertEqual(self.xml.check, False)
        self.assertEqual(self.xml.final, False)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, False)
        self.assertEqual(self.xml.plain, False)

    def test_interfaces_ethernet_lan0_address_space(self):
        last = self.xml.traverse("interfaces ethernet lan0 address ")
        self.assertEqual(last, '')
        self.assertEqual(self.xml.inside, ['interfaces', 'ethernet', 'address'])
        self.assertEqual(self.xml.options, [])
        self.assertEqual(self.xml.filling, False)
        self.assertEqual(self.xml.word, last)
        self.assertEqual(self.xml.check, False)
        self.assertEqual(self.xml.final, False)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, False)
        self.assertEqual(self.xml.plain, False)

    def test_interfaces_ethernet_lan0_address_space_11(self):
        last = self.xml.traverse("interfaces ethernet lan0 address 1.1")
        self.assertEqual(last, '1.1')
        self.assertEqual(self.xml.inside, ['interfaces', 'ethernet', 'address'])
        self.assertEqual(self.xml.options, [])
        self.assertEqual(self.xml.filling, True)
        self.assertEqual(self.xml.word, last)
        self.assertEqual(self.xml.check, True)
        self.assertEqual(self.xml.final, True)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, True)
        self.assertEqual(self.xml.plain, False)

    def test_interfaces_ethernet_lan0_address_space_1111_32(self):
        last = self.xml.traverse("interfaces ethernet lan0 address 1.1.1.1/32")
        self.assertEqual(last, '1.1.1.1/32')
        self.assertEqual(self.xml.inside, ['interfaces', 'ethernet', 'address'])
        self.assertEqual(self.xml.options, [])
        self.assertEqual(self.xml.filling, True)
        self.assertEqual(self.xml.word, last)
        self.assertEqual(self.xml.check, True)
        self.assertEqual(self.xml.final, True)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, True)
        self.assertEqual(self.xml.plain, False)

    def test_interfaces_ethernet_lan0_address_space_1111_32_space(self):
        last = self.xml.traverse("interfaces ethernet lan0 address 1.1.1.1/32 ")
        self.assertEqual(last, '1.1.1.1/32')
        self.assertEqual(self.xml.inside, ['interfaces', 'ethernet', 'address'])
        self.assertEqual(self.xml.options, [])
        self.assertEqual(self.xml.filling, True)
        self.assertEqual(self.xml.word, last)
        self.assertEqual(self.xml.check, True)
        self.assertEqual(self.xml.final, True)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, True)
        self.assertEqual(self.xml.plain, False)

    def test_interfaces_ethernet_lan0_address_space_1111_32_space_text(self):
        last = self.xml.traverse("interfaces ethernet lan0 address 1.1.1.1/32 text")
        self.assertEqual(last, '1.1.1.1/32 text')
        self.assertEqual(self.xml.inside, ['interfaces', 'ethernet', 'address'])
        self.assertEqual(self.xml.options, [])
        self.assertEqual(self.xml.filling, True)
        self.assertEqual(self.xml.word, last)
        self.assertEqual(self.xml.check, True)
        self.assertEqual(self.xml.final, True)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, True)
        self.assertEqual(self.xml.plain, False)

    def test_interfaces_ethernet_lan0_address_space_1111_32_space_text_space(self):
        last = self.xml.traverse("interfaces ethernet lan0 address 1.1.1.1/32 text ")
        self.assertEqual(last, '1.1.1.1/32 text')
        self.assertEqual(self.xml.inside, ['interfaces', 'ethernet', 'address'])
        self.assertEqual(self.xml.options, [])
        self.assertEqual(self.xml.filling, True)
        self.assertEqual(self.xml.word, last)
        self.assertEqual(self.xml.check, True)
        self.assertEqual(self.xml.final, True)
        self.assertEqual(self.xml.extra, False)
        self.assertEqual(self.xml.filled, True)
        self.assertEqual(self.xml.plain, False)

    # Need to add a check for a valuless leafNode