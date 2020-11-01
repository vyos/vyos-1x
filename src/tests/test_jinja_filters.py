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

from unittest import TestCase

from ipaddress import ip_network
from vyos.template import vyos_address_from_cidr
from vyos.template import vyos_netmask_from_cidr
from vyos.template import vyos_ipv4
from vyos.template import vyos_ipv6

class TestTeamplteHelpers(TestCase):
    def setUp(self):
        pass

    def test_helpers_from_cidr(self):
        network_v4 = '192.0.2.0/26'
        self.assertEqual(vyos_address_from_cidr(network_v4), str(ip_network(network_v4).network_address))
        self.assertEqual(vyos_netmask_from_cidr(network_v4), str(ip_network(network_v4).netmask))

    def test_helpers_ipv4(self):
        self.assertTrue(vyos_ipv4('192.0.2.1'))
        self.assertTrue(vyos_ipv4('192.0.2.0/24'))
        self.assertTrue(vyos_ipv4('192.0.2.1/32'))
        self.assertTrue(vyos_ipv4('10.255.1.2'))
        self.assertTrue(vyos_ipv4('10.255.1.0/24'))
        self.assertTrue(vyos_ipv4('10.255.1.2/32'))
        self.assertFalse(vyos_ipv4('2001:db8::'))
        self.assertFalse(vyos_ipv4('2001:db8::1'))
        self.assertFalse(vyos_ipv4('2001:db8::/64'))

    def test_helpers_ipv6(self):
        self.assertFalse(vyos_ipv6('192.0.2.1'))
        self.assertFalse(vyos_ipv6('192.0.2.0/24'))
        self.assertFalse(vyos_ipv6('192.0.2.1/32'))
        self.assertFalse(vyos_ipv6('10.255.1.2'))
        self.assertFalse(vyos_ipv6('10.255.1.0/24'))
        self.assertFalse(vyos_ipv6('10.255.1.2/32'))
        self.assertTrue(vyos_ipv6('2001:db8::'))
        self.assertTrue(vyos_ipv6('2001:db8::1'))
        self.assertTrue(vyos_ipv6('2001:db8::1/64'))
        self.assertTrue(vyos_ipv6('2001:db8::/32'))
        self.assertTrue(vyos_ipv6('2001:db8::/64'))

