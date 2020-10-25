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

from vyos.template import vyos_address_from_cidr
from vyos.template import vyos_netmask_from_cidr


class TestTeamplteHelpers(TestCase):
    def setUp(self):
        pass

    def test_helpers_from_cidr(self):
        network = '192.0.2.0/26'
        self.assertEqual(vyos_address_from_cidr(network), '192.0.2.0')
        self.assertEqual(vyos_netmask_from_cidr(network), '255.255.255.192')

