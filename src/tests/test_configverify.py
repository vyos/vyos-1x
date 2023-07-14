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
from vyos.configverify import verify_diffie_hellman_length
from vyos.utils.process import cmd

dh_file = '/tmp/dh.pem'

class TestDictSearch(TestCase):
    def setUp(self):
        pass

    def test_dh_key_none(self):
        self.assertFalse(verify_diffie_hellman_length('/tmp/non_existing_file', '1024'))

    def test_dh_key_512(self):
        key_len = '512'
        cmd(f'openssl dhparam -out {dh_file} {key_len}')
        self.assertTrue(verify_diffie_hellman_length(dh_file, key_len))
