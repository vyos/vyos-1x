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
from vyos.util import *

class TestVyOSUtil(TestCase):
    def test_key_mangline(self):
        data = {"foo-bar": {"baz-quux": None}}
        expected_data = {"foo_bar": {"baz_quux": None}}
        new_data = mangle_dict_keys(data, '-', '_')
        self.assertEqual(new_data, expected_data)

    def test_sysctl_read(self):
        self.assertEqual(sysctl_read('net.ipv4.conf.lo.forwarding'), '1')

    def test_camel_to_snake_case(self):
        self.assertEqual(camel_to_snake_case('ConnectionTimeout'),
                                             'connection_timeout')
        self.assertEqual(camel_to_snake_case('connectionTimeout'),
                                             'connection_timeout')
        self.assertEqual(camel_to_snake_case('TCPConnectionTimeout'),
                                             'tcp_connection_timeout')
        self.assertEqual(camel_to_snake_case('TCPPort'),
                                             'tcp_port')
        self.assertEqual(camel_to_snake_case('UseHTTPProxy'),
                                             'use_http_proxy')
        self.assertEqual(camel_to_snake_case('CustomerID'),
                                             'customer_id')
