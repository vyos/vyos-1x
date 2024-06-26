# Copyright (C) 2020-2024 VyOS maintainers and contributors
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
from vyos.utils.dict import dict_search
from vyos.utils.dict import dict_search_recursive

data = {
    'string': 'fooo',
    'nested': {'string': 'bar', 'empty': '', 'list': ['foo', 'bar']},
    'non': {},
    'list': ['bar', 'baz'],
    'dict': {'key_1': {}, 'key_2': 'vyos'},
    'interfaces': {'dummy': {'dum0': {'address': ['192.0.2.17/29']}},
                'ethernet': {'eth0': {'address': ['2001:db8::1/64', '192.0.2.1/29'],
                                      'description': 'Test123',
                                      'duplex': 'auto',
                                      'hw_id': '00:00:00:00:00:01',
                                      'speed': 'auto'},
                             'eth1': {'address': ['192.0.2.9/29'],
                                      'description': 'Test456',
                                      'duplex': 'auto',
                                      'hw_id': '00:00:00:00:00:02',
                                      'speed': 'auto'}}}
}

class TestDictSearch(TestCase):
    def setUp(self):
        pass

    def test_non_existing_keys(self):
        # TestDictSearch: Return False when querying for non-existent key
        self.assertEqual(dict_search('non_existing', data), None)
        self.assertEqual(dict_search('non.existing.fancy.key', data), None)

    def test_string(self):
        # TestDictSearch: Return value when querying string
        self.assertEqual(dict_search('string', data), data['string'])

    def test_list(self):
        # TestDictSearch: Return list items when querying list
        self.assertEqual(dict_search('list', data), data['list'])

    def test_dict_key_value(self):
        # TestDictSearch: Return dictionary keys value when value is present
        self.assertEqual(dict_search('dict.key_2', data), data['dict']['key_2'])

    def test_nested_dict_key_value(self):
        # TestDictSearch: Return string value of last key when querying for a nested string
        self.assertEqual(dict_search('nested.string', data), data['nested']['string'])

    def test_nested_dict_key_empty(self):
        # TestDictSearch: Return False when querying for a nested string whose last key is empty
        self.assertEqual(dict_search('nested.empty', data), '')
        self.assertFalse(dict_search('nested.empty', data))

    def test_nested_list(self):
        # TestDictSearch: Return list items when querying nested list
        self.assertEqual(dict_search('nested.list', data), data['nested']['list'])

    def test_invalid_input(self):
        # TestDictSearch: Return list items when querying nested list
        self.assertEqual(dict_search('nested.list', None), None)
        self.assertEqual(dict_search(None, data), None)

    def test_dict_search_recursive(self):
        # Test nested search in dictionary
        tmp = list(dict_search_recursive(data, 'hw_id'))
        self.assertEqual(len(tmp), 2)
        tmp = list(dict_search_recursive(data, 'address'))
        self.assertEqual(len(tmp), 3)
