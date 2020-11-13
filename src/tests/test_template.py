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
