#!/usr/bin/env python3
#
# Copyright (C) 2020-2022 VyOS maintainers and contributors
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
from vyos.util import mangle_dict_keys

class TestVyOSUtil(TestCase):
    def test_key_mangline(self):
        data = {"foo-bar": {"baz-quux": None}}
        expected_data = {"foo_bar": {"baz_quux": None}}
        new_data = mangle_dict_keys(data, '-', '_')
        self.assertEqual(new_data, expected_data)

    def test_sysctl_read(self):
        self.assertEqual(sysctl_read('net.ipv4.conf.lo.forwarding'), '1')

    def test_ipv6_enabled(self):
        tmp = sysctl_read('net.ipv6.conf.all.disable_ipv6')
        # We need to test for both variants as this depends on how the
        # Docker container is started (with or without IPv6 support) - so we
        # will simply check both cases to not make the users life miserable.
        if tmp == '0':
            self.assertTrue(is_ipv6_enabled())
        else:
            self.assertFalse(is_ipv6_enabled())
