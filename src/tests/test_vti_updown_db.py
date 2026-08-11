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

import os
import tempfile
import unittest

from unittest.mock import MagicMock, patch

import vyos.utils.vti_updown_db as _vti_mod
from vyos.utils.vti_updown_db import VTIUpDownDB


class TestVTIUpDownDBLogic(unittest.TestCase):
    """Exercise the in-memory DB API without calling commit()."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(delete=False)
        self.tmpfile.close()
        self._path_patcher = patch.object(
            _vti_mod, 'VTI_WANT_UP_IFLIST', self.tmpfile.name
        )
        self._path_patcher.start()

    def tearDown(self):
        self._path_patcher.stop()
        if os.path.exists(self.tmpfile.name):
            os.unlink(self.tmpfile.name)

    def test_add_makes_interface_wanted_up(self):
        """add() marks the interface as wanted-up."""
        from vyos.utils.vti_updown_db import open_vti_updown_db_for_create_or_update

        with patch('vyos.utils.vti_updown_db.Lock', MagicMock()):
            with open_vti_updown_db_for_create_or_update() as db:
                db.add('vti0', 'conn-a', 'IKEv2')
                self.assertTrue(db.wantsInterfaceUp('vti0'))

    def test_remove_clears_interface(self):
        """remove() clears the entry; wantsInterfaceUp returns False when no entries remain."""
        from vyos.utils.vti_updown_db import open_vti_updown_db_for_create_or_update

        with patch('vyos.utils.vti_updown_db.Lock', MagicMock()):
            with open_vti_updown_db_for_create_or_update() as db:
                db.add('vti0', 'conn-a', 'IKEv2')
                db.remove('vti0', 'conn-a', 'IKEv2')
                self.assertFalse(db.wantsInterfaceUp('vti0'))

    def test_multiple_connections_same_interface(self):
        """Interface stays wanted-up until all its connection entries are removed."""
        from vyos.utils.vti_updown_db import open_vti_updown_db_for_create_or_update

        with patch('vyos.utils.vti_updown_db.Lock', MagicMock()):
            with open_vti_updown_db_for_create_or_update() as db:
                db.add('vti0', 'conn-a', 'IKEv2')
                db.add('vti0', 'conn-b', 'IKEv2')
                db.remove('vti0', 'conn-a', 'IKEv2')
                # conn-b still present
                self.assertTrue(db.wantsInterfaceUp('vti0'))
                db.remove('vti0', 'conn-b', 'IKEv2')
                self.assertFalse(db.wantsInterfaceUp('vti0'))

    def test_concurrent_sas_same_connection(self):
        """Connection entries are counted, not deduplicated.

        A peer that re-establishes a tunnel before the local side has timed the
        old IKE_SA out leaves two CHILD_SAs of the same connection installed at
        once, and the hook fires up-client twice with identical arguments. The
        teardown of the first must not bring down an interface the second is
        still carrying.
        """
        from vyos.utils.vti_updown_db import open_vti_updown_db_for_create_or_update

        with patch('vyos.utils.vti_updown_db.Lock', MagicMock()):
            with open_vti_updown_db_for_create_or_update() as db:
                db.add('vti0', 'conn-a', 'IKEv2')
                db.add('vti0', 'conn-a', 'IKEv2')
                db.remove('vti0', 'conn-a', 'IKEv2')
                # the second CHILD_SA is still installed
                self.assertTrue(db.wantsInterfaceUp('vti0'))
                db.remove('vti0', 'conn-a', 'IKEv2')
                self.assertFalse(db.wantsInterfaceUp('vti0'))

    def test_duplicate_entries_survive_a_reload(self):
        """Occurrences are preserved across a file round-trip.

        The two CHILD_SAs that produce them are rarely torn down in the same DB
        session, so the count has to survive being written out and read back --
        reading into a set would silently collapse it.
        """
        with open(self.tmpfile.name, 'w') as f:
            f.write('vti0:conn-a:IKEv2 vti0:conn-a:IKEv2')

        from vyos.utils.vti_updown_db import open_vti_updown_db_for_create_or_update

        with patch('vyos.utils.vti_updown_db.Lock', MagicMock()):
            with open_vti_updown_db_for_create_or_update() as db:
                db.remove('vti0', 'conn-a', 'IKEv2')
                self.assertTrue(db.wantsInterfaceUp('vti0'))
                db.remove('vti0', 'conn-a', 'IKEv2')
                self.assertFalse(db.wantsInterfaceUp('vti0'))

    def test_persistent_entries_are_not_counted(self):
        """Persistent entries stay unique, so one remove() always clears them."""
        from vyos.utils.vti_updown_db import open_vti_updown_db_for_create_or_update

        with patch('vyos.utils.vti_updown_db.Lock', MagicMock()):
            with open_vti_updown_db_for_create_or_update() as db:
                db.add('vti0')
                db.add('vti0')
                db.remove('vti0')
                self.assertFalse(db.wantsInterfaceUp('vti0'))

    def test_remove_all_other_interfaces(self):
        """removeAllOtherInterfaces() drops entries for interfaces not in the keep list."""
        from vyos.utils.vti_updown_db import open_vti_updown_db_for_create_or_update

        with patch('vyos.utils.vti_updown_db.Lock', MagicMock()):
            with open_vti_updown_db_for_create_or_update() as db:
                db.add('vti0', 'conn-a', 'IKEv2')
                db.add('vti1', 'conn-b', 'IKEv2')
                db.removeAllOtherInterfaces(['vti0'])
                self.assertTrue(db.wantsInterfaceUp('vti0'))
                self.assertFalse(db.wantsInterfaceUp('vti1'))

    def test_set_persistent_interfaces(self):
        """setPersistentInterfaces() adds bare-name (persistent) entries."""
        from vyos.utils.vti_updown_db import open_vti_updown_db_for_create_or_update

        with patch('vyos.utils.vti_updown_db.Lock', MagicMock()):
            with open_vti_updown_db_for_create_or_update() as db:
                db.setPersistentInterfaces(['vti0', 'vti1'])
                # Persistent entries have no colon in the ifspec.
                persistent = {s for s in db._ifspecs if ':' not in s}
                self.assertEqual(persistent, {'vti0', 'vti1'})
                self.assertTrue(db.wantsInterfaceUp('vti0'))
                self.assertTrue(db.wantsInterfaceUp('vti1'))

    def test_seed_from_file(self):
        """VTIUpDownDB reads pre-existing entries from the file on open."""
        with open(self.tmpfile.name, 'w') as f:
            f.write('vti0:conn-a:IKEv2 vti1:conn-b:IKEv2')

        from vyos.utils.vti_updown_db import open_vti_updown_db_readonly

        with patch('vyos.utils.vti_updown_db.Lock', MagicMock()):
            with open_vti_updown_db_readonly() as db:
                self.assertTrue(db.wantsInterfaceUp('vti0'))
                self.assertTrue(db.wantsInterfaceUp('vti1'))

    def test_readonly_yields_none_when_db_absent(self):
        """open_vti_updown_db_readonly() yields None (no raise) when the DB file is absent."""
        from vyos.utils.vti_updown_db import open_vti_updown_db_readonly

        # Point at a path that does not exist.
        missing = os.path.join(tempfile.gettempdir(), 'nonexistent_vti_updown_db_test')
        if os.path.exists(missing):
            os.unlink(missing)
        with patch.object(_vti_mod, 'VTI_WANT_UP_IFLIST', missing):
            with patch('vyos.utils.vti_updown_db.Lock', MagicMock()):
                with open_vti_updown_db_readonly() as db:
                    self.assertIsNone(db)


class TestVTIUpDownDBLockWiring(unittest.TestCase):
    """Verify Lock is acquired before yielding and released on context exit."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(delete=False)
        self.tmpfile.close()
        self._path_patcher = patch.object(
            _vti_mod, 'VTI_WANT_UP_IFLIST', self.tmpfile.name
        )
        self._path_patcher.start()

    def tearDown(self):
        self._path_patcher.stop()
        if os.path.exists(self.tmpfile.name):
            os.unlink(self.tmpfile.name)

    def _make_lock_mock(self):
        lock_instance = MagicMock()
        lock_cls = MagicMock(return_value=lock_instance)
        return lock_cls, lock_instance

    def test_create_or_update_acquires_and_releases(self):
        """open_vti_updown_db_for_create_or_update() acquires the lock before yielding and releases it on exit."""
        from vyos.utils.vti_updown_db import open_vti_updown_db_for_create_or_update

        lock_cls, lock_inst = self._make_lock_mock()
        with patch('vyos.utils.vti_updown_db.Lock', lock_cls):
            with open_vti_updown_db_for_create_or_update() as _db:
                lock_inst.acquire.assert_called_once()
                lock_inst.release.assert_not_called()
            lock_inst.release.assert_called_once()

    def test_update_acquires_and_releases(self):
        """open_vti_updown_db_for_update() acquires the lock before yielding and releases it on exit."""
        from vyos.utils.vti_updown_db import open_vti_updown_db_for_update

        lock_cls, lock_inst = self._make_lock_mock()
        with patch('vyos.utils.vti_updown_db.Lock', lock_cls):
            with open_vti_updown_db_for_update() as _db:
                lock_inst.acquire.assert_called_once()
                lock_inst.release.assert_not_called()
            lock_inst.release.assert_called_once()

    def test_readonly_acquires_and_releases(self):
        """open_vti_updown_db_readonly() acquires the lock before yielding and releases it on exit."""
        from vyos.utils.vti_updown_db import open_vti_updown_db_readonly

        lock_cls, lock_inst = self._make_lock_mock()
        with patch('vyos.utils.vti_updown_db.Lock', lock_cls):
            with open_vti_updown_db_readonly() as _db:
                lock_inst.acquire.assert_called_once()
                lock_inst.release.assert_not_called()
            lock_inst.release.assert_called_once()


class TestRemoveVTIUpDownDBLockOrdering(unittest.TestCase):
    """remove_vti_updown_db() must hold the lock across os.unlink."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(delete=False)
        self.tmpfile.close()
        self._path_patcher = patch.object(
            _vti_mod, 'VTI_WANT_UP_IFLIST', self.tmpfile.name
        )
        self._path_patcher.start()

    def tearDown(self):
        self._path_patcher.stop()
        # File may have been unlinked by the function under test.
        if os.path.exists(self.tmpfile.name):
            os.unlink(self.tmpfile.name)

    def test_lock_held_across_unlink(self):
        """os.unlink fires before lock.release(), proving the lock covers the unlink."""
        from vyos.utils.vti_updown_db import remove_vti_updown_db

        lock_inst = MagicMock()
        lock_cls = MagicMock(return_value=lock_inst)

        # Record lock.release call_count at the moment os.unlink fires.
        release_count_at_unlink = []

        def _observe_unlink(path):
            release_count_at_unlink.append(lock_inst.release.call_count)

        with patch('vyos.utils.vti_updown_db.Lock', lock_cls):
            with patch.object(VTIUpDownDB, 'commit'):
                with patch.object(_vti_mod.os, 'unlink', side_effect=_observe_unlink):
                    remove_vti_updown_db()

        lock_inst.acquire.assert_called_once()
        lock_inst.release.assert_called_once()
        self.assertTrue(release_count_at_unlink, 'os.unlink was never called')
        self.assertEqual(
            release_count_at_unlink[0],
            0,
            'lock.release() was called before os.unlink -- unlink is not protected by the lock',
        )

    def test_remove_noop_when_db_absent(self):
        """remove_vti_updown_db() returns without raising and does not unlink when the DB is absent."""
        from vyos.utils.vti_updown_db import remove_vti_updown_db

        # No DB file present.
        os.unlink(self.tmpfile.name)
        self.assertFalse(os.path.exists(self.tmpfile.name))

        lock_inst = MagicMock()
        lock_cls = MagicMock(return_value=lock_inst)

        with patch('vyos.utils.vti_updown_db.Lock', lock_cls):
            with patch.object(
                _vti_mod.os,
                'unlink',
                side_effect=AssertionError('os.unlink must not be called'),
            ) as unlink_mock:
                remove_vti_updown_db()
                unlink_mock.assert_not_called()

        lock_inst.acquire.assert_called_once()
        lock_inst.release.assert_called_once()


if __name__ == '__main__':
    unittest.main()
