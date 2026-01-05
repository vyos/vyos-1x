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

class TestVyOSUtils(TestCase):
    def test_key_mangling(self):
        from vyos.utils.dict import mangle_dict_keys
        data = {"foo-bar": {"baz-quux": None}}
        expected_data = {"foo_bar": {"baz_quux": None}}
        new_data = mangle_dict_keys(data, '-', '_')
        self.assertEqual(new_data, expected_data)

    def test_sysctl_read(self):
        from vyos.utils.system import sysctl_read
        self.assertEqual(sysctl_read('net.ipv4.conf.lo.forwarding'), '1')

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
