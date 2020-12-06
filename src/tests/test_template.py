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

import vyos.template
from unittest import TestCase

class TestVyOSTemplate(TestCase):
    def setUp(self):
        pass

    def test_is_ip(self):
        self.assertTrue(vyos.template.is_ip('192.0.2.1'))
        self.assertTrue(vyos.template.is_ip('2001:db8::1'))
        self.assertFalse(vyos.template.is_ip('VyOS'))

    def test_is_ipv4(self):
        self.assertTrue(vyos.template.is_ipv4('192.0.2.1'))
        self.assertTrue(vyos.template.is_ipv4('192.0.2.0/24'))
        self.assertTrue(vyos.template.is_ipv4('192.0.2.1/32'))

        self.assertFalse(vyos.template.is_ipv4('2001:db8::1'))
        self.assertFalse(vyos.template.is_ipv4('2001:db8::/64'))
        self.assertFalse(vyos.template.is_ipv4('VyOS'))

    def test_is_ipv6(self):
        self.assertTrue(vyos.template.is_ipv6('2001:db8::1'))
        self.assertTrue(vyos.template.is_ipv6('2001:db8::/64'))
        self.assertTrue(vyos.template.is_ipv6('2001:db8::1/64'))

        self.assertFalse(vyos.template.is_ipv6('192.0.2.1'))
        self.assertFalse(vyos.template.is_ipv6('192.0.2.0/24'))
        self.assertFalse(vyos.template.is_ipv6('192.0.2.1/32'))
        self.assertFalse(vyos.template.is_ipv6('VyOS'))

    def test_address_from_cidr(self):
        self.assertEqual(vyos.template.address_from_cidr('192.0.2.0/24'),  '192.0.2.0')
        self.assertEqual(vyos.template.address_from_cidr('2001:db8::/48'), '2001:db8::')

        with self.assertRaises(ValueError):
            # ValueError: 192.0.2.1/24 has host bits set
            self.assertEqual(vyos.template.address_from_cidr('192.0.2.1/24'),  '192.0.2.1')

        with self.assertRaises(ValueError):
            # ValueError: 2001:db8::1/48 has host bits set
            self.assertEqual(vyos.template.address_from_cidr('2001:db8::1/48'), '2001:db8::1')

    def test_netmask_from_cidr(self):
        self.assertEqual(vyos.template.netmask_from_cidr('192.0.2.0/24'),  '255.255.255.0')
        self.assertEqual(vyos.template.netmask_from_cidr('192.0.2.128/25'),  '255.255.255.128')
        self.assertEqual(vyos.template.netmask_from_cidr('2001:db8::/48'), 'ffff:ffff:ffff::')

        with self.assertRaises(ValueError):
            # ValueError: 192.0.2.1/24 has host bits set
            self.assertEqual(vyos.template.netmask_from_cidr('192.0.2.1/24'),  '255.255.255.0')

        with self.assertRaises(ValueError):
            # ValueError: 2001:db8:1:/64 has host bits set
            self.assertEqual(vyos.template.netmask_from_cidr('2001:db8:1:/64'), 'ffff:ffff:ffff:ffff::')

    def test_first_host_address(self):
        self.assertEqual(vyos.template.first_host_address('10.0.0.0/24'),  '10.0.0.1')
        self.assertEqual(vyos.template.first_host_address('10.0.0.128/25'),  '10.0.0.129')
        self.assertEqual(vyos.template.first_host_address('2001:db8::/64'),  '2001:db8::')

    def test_last_host_address(self):
        self.assertEqual(vyos.template.last_host_address('10.0.0.0/24'),  '10.0.0.254')
        self.assertEqual(vyos.template.last_host_address('10.0.0.128/25'),  '10.0.0.254')
        self.assertEqual(vyos.template.last_host_address('2001:db8::/64'),  '2001:db8::ffff:ffff:ffff:ffff')

    def test_increment_ip(self):
        self.assertEqual(vyos.template.inc_ip('10.0.0.0/24', '2'),  '10.0.0.2')
        self.assertEqual(vyos.template.inc_ip('10.0.0.0', '2'),  '10.0.0.2')
        self.assertEqual(vyos.template.inc_ip('10.0.0.0', '10'),  '10.0.0.10')
        self.assertEqual(vyos.template.inc_ip('2001:db8::/64', '2'),  '2001:db8::2')
        self.assertEqual(vyos.template.inc_ip('2001:db8::', '10'),  '2001:db8::a')

    def test_decrement_ip(self):
        self.assertEqual(vyos.template.dec_ip('10.0.0.100/24', '1'),  '10.0.0.99')
        self.assertEqual(vyos.template.dec_ip('10.0.0.90', '10'),  '10.0.0.80')
        self.assertEqual(vyos.template.dec_ip('2001:db8::b/64', '10'),  '2001:db8::1')
        self.assertEqual(vyos.template.dec_ip('2001:db8::f', '5'),  '2001:db8::a')

