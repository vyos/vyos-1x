# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
from unittest.mock import patch

class TestVyOSUtils(TestCase):
    def test_key_mangling(self):
        from vyos.utils.dict import mangle_dict_keys
        data = {"foo-bar": {"baz-quux": None}}
        expected_data = {"foo_bar": {"baz_quux": None}}
        new_data = mangle_dict_keys(data, '-', '_')
        self.assertEqual(new_data, expected_data)

    def test_sysctl_read(self):
        from vyos.utils.system import sysctl_read
        self.assertEqual(sysctl_read(['net', 'ipv4', 'conf', 'lo', 'forwarding']), '1')

    def test_sysctl_key_normalization(self):
        from vyos.utils.system import sysctl_read
        with patch('vyos.utils.system.run') as mock_run:
            mock_run.return_value.stdout = b'1\n'
            sysctl_read(['net', 'ipv4', 'conf', 'eth0.10', 'forwarding'])
            mock_run.assert_called_with(
                ['sysctl', '-nb', 'net.ipv4.conf.eth0/10.forwarding'],
                capture_output=True,
            )

    def test_list_strip(self):
        from vyos.utils.list import list_strip

        lst = ['a', 'b', 'c', 'd', 'e']
        sub = ['a', 'b']
        rsb = ['d', 'e']
        non = ['a', 'e']
        self.assertEqual(list_strip(lst, sub), ['c', 'd', 'e'])
        self.assertEqual(list_strip(lst, rsb, right=True), ['a', 'b', 'c'])
        self.assertEqual(list_strip(lst, non), [])
        self.assertEqual(list_strip(sub, lst), [])

    def test_range_str_to_list(self):
        from vyos.utils.convert import range_str_to_list

        # basic cases
        self.assertEqual(range_str_to_list('1-3'), [1, 2, 3])
        self.assertEqual(range_str_to_list('1-3,5,7-8'), [1, 2, 3, 5, 7, 8])
        self.assertEqual(range_str_to_list('3'), [3])
        # empty string
        self.assertEqual(range_str_to_list(''), [])
        # unordered input
        self.assertEqual(range_str_to_list('5,1-3,4'), [1, 2, 3, 4, 5])
        self.assertEqual(range_str_to_list('7-9,1-3'), [1, 2, 3, 7, 8, 9])
        # overlapping ranges
        self.assertEqual(range_str_to_list('1-5,3-7'), [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(range_str_to_list('1-3,2-4,3-5'), [1, 2, 3, 4, 5])
        # duplicated values
        self.assertEqual(range_str_to_list('1,1,2,2,3'), [1, 2, 3])
        self.assertEqual(range_str_to_list('5,1-3,2,3'), [1, 2, 3, 5])
        # adjacent ranges
        self.assertEqual(range_str_to_list('1-3,4-6'), [1, 2, 3, 4, 5, 6])

    def test_list_to_range_str(self):
        from vyos.utils.convert import list_to_range_str

        # basic cases
        self.assertEqual(list_to_range_str([1, 2, 3]), '1-3')
        self.assertEqual(list_to_range_str([1, 2, 3, 5, 7, 8]), '1-3,5,7-8')
        self.assertEqual(list_to_range_str([1, 3]), '1,3')
        self.assertEqual(list_to_range_str([3]), '3')
        # empty list
        self.assertEqual(list_to_range_str([]), '')
        # unordered input
        self.assertEqual(list_to_range_str([5, 1, 2, 3, 4]), '1-5')
        self.assertEqual(list_to_range_str([7, 8, 9, 1, 2, 3]), '1-3,7-9')
        # duplicated values
        self.assertEqual(list_to_range_str([1, 1, 2, 2, 3, 3]), '1-3')
        self.assertEqual(list_to_range_str([5, 1, 2, 2, 3, 5]), '1-3,5')
