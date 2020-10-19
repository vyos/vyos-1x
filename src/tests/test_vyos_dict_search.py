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

import unittest
from unittest import TestCase

from vyos.util import vyos_dict_search

data = {
    'string': 'fooo',
    'nested': {'string': 'bar', 'empty': '', 'list': ['foo', 'bar']},
    'list': ['bar', 'baz'],
    'dict': {'key_1': {}, 'key_2': 'vyos'}
}

class TestDictSearch(TestCase):
    def setUp(self):
        pass

    def test_non_existing_keys(self):
        """ TestDictSearch: Return False when querying for non-existent key """
        self.assertFalse(vyos_dict_search('non_existing', data))

    def test_string(self):
        """ TestDictSearch: Return value when querying string """
        self.assertEqual(vyos_dict_search('string', data), data['string'])

    def test_list(self):
        """ TestDictSearch: Return list items when querying list """
        self.assertEqual(vyos_dict_search('list', data), data['list'])

    def test_dict_key_value(self):
        """ TestDictSearch: Return dictionary keys value when value is present """
        self.assertEqual(vyos_dict_search('dict.key_2', data), data['dict']['key_2'])

    def test_nested_dict_key_value(self):
        """ TestDictSearch: Return string value of last key when querying for a nested string """
        self.assertEqual(vyos_dict_search('nested.string', data), data['nested']['string'])

    def test_nested_dict_key_empty(self):
        """ TestDictSearch: Return False when querying for a nested string whose last key is empty """
        self.assertFalse(vyos_dict_search('nested.empty', data))

    def test_nested_list(self):
        """ TestDictSearch: Return list items when querying nested list """
        self.assertEqual(vyos_dict_search('nested.list', data), data['nested']['list'])
