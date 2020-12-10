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

import vyos.validate
from unittest import TestCase

class TestVyOSValidate(TestCase):
    def setUp(self):
        pass

    def test_is_addr_assigned(self):
        self.assertTrue(vyos.validate.is_addr_assigned('127.0.0.1'))
        self.assertTrue(vyos.validate.is_addr_assigned('::1'))
        self.assertFalse(vyos.validate.is_addr_assigned('127.251.255.123'))

    def test_is_ipv6_link_local(self):
        self.assertFalse(vyos.validate.is_ipv6_link_local('169.254.0.1'))
        self.assertTrue(vyos.validate.is_ipv6_link_local('fe80::'))
        self.assertTrue(vyos.validate.is_ipv6_link_local('fe80::affe:1'))
        self.assertFalse(vyos.validate.is_ipv6_link_local('2001:db8::'))
        self.assertFalse(vyos.validate.is_ipv6_link_local('VyOS'))

    def test_is_ipv6_link_local(self):
        self.assertTrue(vyos.validate.is_loopback_addr('127.0.0.1'))
        self.assertTrue(vyos.validate.is_loopback_addr('127.0.1.1'))
        self.assertTrue(vyos.validate.is_loopback_addr('127.1.1.1'))
        self.assertTrue(vyos.validate.is_loopback_addr('::1'))

        self.assertFalse(vyos.validate.is_loopback_addr('::2'))
        self.assertFalse(vyos.validate.is_loopback_addr('192.0.2.1'))



