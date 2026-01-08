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
import unittest

from vyos.utils import auth

class TestVyOSUtilsAuth(unittest.TestCase):
    def test_uid_root(self):
        self.assertEqual(auth.get_local_passwd_entries(0).pw_name, 'root')
        self.assertEqual(auth.get_local_passwd_entries(0).pw_uid, 0)

    def test_uid_daemon(self):
        uid = None
        for user in auth.get_local_passwd_entries():
            if user.pw_name == 'daemon':
                uid = user.pw_uid
                break

        self.assertEqual(auth.get_local_passwd_entries(uid).pw_name, 'daemon')
        self.assertEqual(auth.get_local_passwd_entries(uid).pw_uid, uid)

    def test_uid_not_found(self):
        self.assertEqual(auth.get_local_passwd_entries(5465487635), None)

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
