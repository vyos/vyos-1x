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

import pwd
from unittest import TestCase

from vyos.utils import auth


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

class TestVyOSUtilsAuth(TestCase):

    def test_get_local_users_returns_existing_usernames(self):
        # Returned users exist, skip list is excluded, and UIDs are in range

        all_users = set(s_user.pw_name for s_user in pwd.getpwall())
        local_users = auth.get_local_users()

        # All returned users must really exist
        for user in local_users:
            self.assertIn(user, all_users)

        # Nobody in the skip list
        for skipped in auth.SYSTEM_USER_SKIP_LIST:
            self.assertNotIn(skipped, local_users)

        # All are within UID range
        for s_user in pwd.getpwall():
            if s_user.pw_name in local_users:
                self.assertGreaterEqual(s_user.pw_uid, auth.MIN_USER_UID)
                self.assertLessEqual(s_user.pw_uid, auth.MAX_USER_UID)

    def test_get_user_home_dir_for_real_user(self):
        # User's homedir is a non-empty string for a valid user

        local_users = auth.get_local_users()
        if local_users:
            for user in local_users:
                home_dir = auth.get_user_home_dir(user)
                self.assertIsInstance(home_dir, str)
                self.assertTrue(bool(home_dir))  # Should not be empty
        else:
            self.skipTest("No suitable non-system users found on this system")

    def test_get_user_home_dir_invalid_user(self):
        # Raises KeyError for nonexistent username

        user = "__this_user_does_not_exist__"  # Test using unlikely username
        with self.assertRaises(KeyError):
            auth.get_user_home_dir(user)
