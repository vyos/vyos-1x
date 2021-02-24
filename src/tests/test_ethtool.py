#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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
from vyos.ethtool import Ethtool

class TestVyOSEthtool(TestCase):
    def test_ring_buffer(self):
        tmp = Ethtool('lo')
        self.assertEqual(tmp.get_rx_buffer(), None)
        self.assertEqual(tmp.get_tx_buffer(), None)

    def test_fixed_settings(self):
        tmp = Ethtool('lo')
        self.assertTrue(tmp.is_fixed_lro())
        self.assertFalse(tmp.is_fixed_gro())
        self.assertFalse(tmp.is_fixed_gso())
        self.assertFalse(tmp.is_fixed_sg())
