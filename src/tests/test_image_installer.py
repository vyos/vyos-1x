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
#
# Coverage for T9403: preserve /config ownership across an image upgrade.

import os
import shutil
import stat
import tempfile
import unittest
from unittest import mock

from helper import prepare_module

_here = os.path.dirname(__file__)
image_installer = None


def setUpModule():
    """Import image_installer without a real VyOS system

    get_running_image() falls back to reading directories['data']/version.json
    when it can't find a VyOS-style BOOT_IMAGE kernel argument, which is
    always true on the host these tests run on: point it at a throwaway
    file for the import, then put everything back.
    """
    global image_installer
    import vyos.defaults as defaults

    orig_data_dir = defaults.directories['data']
    with tempfile.TemporaryDirectory() as data_dir:
        with open(os.path.join(data_dir, 'version.json'), 'w') as f:
            f.write('{"version": "test"}')
        defaults.directories['data'] = data_dir + '/'
        try:
            image_installer = prepare_module(
                os.path.join(_here, '../op_mode/image_installer.py'), 'image_installer'
            )
        finally:
            defaults.directories['data'] = orig_data_dir


class TreeTestCase(unittest.TestCase):
    """A src and a dst tree in a temporary directory, removed afterwards"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.src = os.path.join(self.tmp, 'src')
        self.dst = os.path.join(self.tmp, 'dst')
        os.mkdir(self.src)
        os.mkdir(self.dst)

    def both(self, func, *args):
        """Run func(tree_root, *args) on src and dst"""
        for root in (self.src, self.dst):
            func(root, *args)


class RecordingTestCase(TreeTestCase):
    """Record lchown()/chmod() calls instead of making them

    Changing an owner needs root; recording the calls doesn't, and says
    exactly which entry got which owner and mode.
    """

    def setUp(self):
        super().setUp()
        self.owners = {}
        self.modes = {}
        for name, func in (('lchown', self._lchown), ('chmod', self._chmod)):
            patcher = mock.patch.object(image_installer, name, func)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _rel(self, path):
        return os.path.relpath(str(path), self.dst)

    def _lchown(self, path, uid, gid):
        self.owners[self._rel(path)] = (uid, gid)

    def _chmod(self, path, mode):
        self.modes[self._rel(path)] = mode


class TestReadIds(TreeTestCase):
    """read_ids() returns {name: id} from a passwd or group file"""

    def read(self, text):
        path = os.path.join(self.tmp, 'passwd')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        return image_installer.read_ids(path)

    def test_names_and_ids(self):
        self.assertEqual(
            self.read('root:x:0:0::/root:/bin/bash\n_kea:x:100:104::/:/bin/false\n'),
            {'root': 0, '_kea': 100},
        )

    def test_first_entry_of_a_name_wins(self):
        self.assertEqual(self.read('frr:x:108:\nfrr:x:200:\n'), {'frr': 108})

    def test_malformed_lines_are_skipped(self):
        self.assertEqual(
            self.read('\nshort:x\nnoid:x::\nneg:x:-1:\nfrr:x:108:\n'), {'frr': 108}
        )

    def test_ids_too_long_for_int_are_skipped(self):
        # int() refuses digit strings over 4300 digits (Python 3.11+)
        self.assertEqual(self.read('huge:x:' + '9' * 5000 + ':\nfrr:x:108:\n'),
                         {'frr': 108})

    def test_non_ascii_digits_are_skipped(self):
        # '²'.isdigit() is True but int('²') raises: one such line used to
        # abort `add system image`.
        self.assertEqual(self.read('odd:x:\u00b2:\nfrr:x:108:\n'), {'frr': 108})


class TestIdMap(TreeTestCase):
    """IdMap translates the ids of the running image into the new one"""

    def idmap(self, old, new):
        files = []
        for name, entries in (('old', old), ('new', new)):
            path = os.path.join(self.tmp, name)
            with open(path, 'w') as f:
                f.writelines(f'{n}:x:{i}:\n' for n, i in entries)
            files.append(path)
        return image_installer.IdMap(*files, kind='uid')

    def test_system_account_follows_its_name(self):
        # 2026.05 -> 2026.10: strongswan removed, everyone after it moved by one
        ids = self.idmap([('_kea', 101), ('frr', 109)], [('_kea', 100), ('frr', 108)])
        self.assertEqual((ids(101), ids(109)), (100, 108))

    def test_root_and_regular_range_keep_their_number(self):
        # radius_user and the tacacs group are 1000 in the image, and 1000:1000
        # is also the most common container user: no translation from 1000 up
        ids = self.idmap(
            [('root', 0), ('radius_user', 1000), ('vyos', 1002)],
            [('root', 0), ('radius_user', 1001)],
        )
        self.assertEqual((ids(0), ids(1000), ids(1002)), (0, 1000, 1002))

    def test_gone_account_whose_number_is_taken_goes_to_root(self):
        ids = self.idmap([('strongswan', 107)], [('zabbix', 107)])
        self.assertEqual(ids(107), 0)

    def test_gone_account_whose_number_is_free_keeps_it(self):
        ids = self.idmap([('salt', 110)], [('frr', 108)])
        self.assertEqual(ids(110), 110)

    def test_unnamed_id_keeps_its_number(self):
        # e.g. a container user: nothing says which host account it would be
        ids = self.idmap([('frr', 108)], [('systemd-network', 998)])
        self.assertEqual((ids(998), ids(4000)), (998, 4000))

    def test_an_id_with_several_names_follows_one_that_survives(self):
        ids = self.idmap(
            [('gone', 120), ('kept', 120)], [('kept', 121), ('other', 120)]
        )
        self.assertEqual(ids(120), 121)

    def test_identity_without_files(self):
        self.assertEqual(image_installer.IdMap()(107), 107)

    def test_warnings_name_only_the_ids_met_with_their_count(self):
        ids = self.idmap(
            [('strongswan', 107), ('salt', 111)],
            [('zabbix', 107), ('_chrony', 111), ('dnsmasq', 998)],
        )
        for i in (107, 107, 998, 111, 4000):
            ids(i)
        warnings = []
        with mock.patch.object(image_installer, 'Warning', warnings.append):
            ids.report('/config')
        self.assertEqual(len(warnings), 3, warnings)
        text = '\n'.join(warnings)
        self.assertIn('2 entries', text)
        self.assertIn('strongswan', text)
        self.assertIn('zabbix', text)
        self.assertIn('dnsmasq', text)
        # also printed on a reinstall, where the running image is the new one
        self.assertNotIn('running image', text)
        self.assertNotIn('4000', text)

    def test_no_warning_when_nothing_is_ambiguous(self):
        ids = self.idmap([('frr', 109)], [('frr', 108)])
        ids(109)
        with mock.patch.object(image_installer, 'Warning') as warning:
            ids.report('/config')
        warning.assert_not_called()


class TestCopyRegularFile(TreeTestCase):
    """The copy_function handed to copytree() for a /config tree"""

    def make_special_files(self, root):
        import socket

        sock = socket.socket(socket.AF_UNIX)
        self.addCleanup(sock.close)
        sock.bind(os.path.join(root, 'ctl.sock'))  # e.g. clamd.sock
        os.mkfifo(os.path.join(root, 'ctl.fifo'))  # e.g. c-icap.ctl
        with open(os.path.join(root, 'conf'), 'w') as f:
            f.write('x')

    def test_sockets_and_fifos_do_not_abort_the_copy(self):
        # With copytree()'s default copy2(), a socket raises ENXIO and a FIFO
        # SpecialFileError, both collected into shutil.Error at the end.
        self.make_special_files(self.src)
        dst = os.path.join(self.dst, 'config')
        shutil.copytree(
            self.src,
            dst,
            symlinks=True,
            copy_function=image_installer.copy_regular_file,
        )
        self.assertEqual(sorted(os.listdir(dst)), ['conf'])

    def test_extended_attributes_are_kept(self):
        # POSIX ACLs are xattrs: the reinstall path used copytree()'s copy2(),
        # which keeps them, before copy_regular_file() replaced it.
        src = os.path.join(self.src, 'conf')
        with open(src, 'w') as f:
            f.write('x')
        try:
            os.setxattr(src, 'user.t9403', b'kept')
        except OSError:
            self.skipTest('no user xattrs on this filesystem')
        dst = os.path.join(self.dst, 'conf')
        image_installer.copy_regular_file(src, dst)
        self.assertEqual(os.getxattr(dst, 'user.t9403'), b'kept')

    def test_ownership_is_left_to_copy_ownership(self):
        with open(os.path.join(self.src, 'conf'), 'w') as f:
            f.write('x')
        with mock.patch.object(image_installer, 'chown') as chown, mock.patch.object(
            image_installer, 'lchown'
        ) as lchown:
            image_installer.copy_regular_file(
                os.path.join(self.src, 'conf'), os.path.join(self.dst, 'conf')
            )
        chown.assert_not_called()
        lchown.assert_not_called()


class TestCopyOwnershipEntries(RecordingTestCase):
    """Which dst entries copy_ownership() gives an owner to"""

    def test_symlink_to_directory_gets_its_owner(self):
        # os.walk() lists a symlink to a directory in `dirs`: pruning `dirs`
        # before handling the entries skipped its lchown().
        self.both(lambda r: os.mkdir(os.path.join(r, 'bar')))
        self.both(lambda r: os.symlink('bar', os.path.join(r, 'foo')))
        image_installer.copy_ownership(self.src, self.dst)
        self.assertIn('foo', self.owners)
        self.assertIn('bar', self.owners)
        self.assertNotIn('foo', self.modes, 'chmod() would follow the link')

    def test_symlink_to_directory_is_not_descended(self):
        self.both(lambda r: os.mkdir(os.path.join(r, 'bar')))
        self.both(lambda r: open(os.path.join(r, 'bar', 'leaf'), 'w').close())
        self.both(lambda r: os.symlink('bar', os.path.join(r, 'foo')))
        image_installer.copy_ownership(self.src, self.dst)
        self.assertNotIn(os.path.join('foo', 'leaf'), self.owners)
        self.assertIn(os.path.join('bar', 'leaf'), self.owners)

    def test_each_destination_entry_is_stated_once(self):
        self.both(lambda r: os.makedirs(os.path.join(r, 'a', 'b')))
        self.both(lambda r: open(os.path.join(r, 'a', 'f'), 'w').close())
        seen = []
        real_lstat = os.lstat

        def counting_lstat(path):
            if os.path.commonpath([str(path), self.dst]) == self.dst:
                seen.append(self._rel(path))
            return real_lstat(path)

        with mock.patch.object(image_installer, 'lstat', counting_lstat):
            image_installer.copy_ownership(self.src, self.dst)
        self.assertEqual(sorted(seen), sorted(set(seen)), 'some entry stated twice')


class TestConfigRoot(RecordingTestCase):
    """The root of /config in the new image is the new image's own"""

    def test_copy_ownership_leaves_the_root_alone(self):
        os.chmod(self.src, 0o755)
        image_installer.copy_ownership(self.src, self.dst)
        self.assertNotIn('.', self.owners)
        self.assertNotIn('.', self.modes)

    def test_copy_config_tree_resets_a_drifted_root(self):
        # A running /config drifted to root:root 0755 must not be carried
        # into the new image: vyattacfg members could no longer write it.
        os.chmod(self.src, 0o755)
        open(os.path.join(self.src, 'config.boot'), 'w').close()
        image_installer.copy_config_tree(
            self.src,
            self.dst,
            image_installer.IdMap(),
            image_installer.IdMap(kind='gid'),
            cfg_gid=102,
        )
        self.assertEqual(self.owners['.'], (0, 102))
        self.assertEqual(self.modes['.'], 0o2775)
        self.assertIn('config.boot', self.owners)

    def test_vyattacfg_gid_is_read_from_the_new_image(self):
        group = os.path.join(self.tmp, 'group')
        with open(group, 'w') as f:
            f.write('users:x:100:\nvyattacfg:x:103:\n')
        self.assertEqual(image_installer.vyattacfg_gid(group), 103)


class TestReinstallPath(TreeTestCase):
    """install image from the live ISO over a previous installation"""

    def setUp(self):
        super().setUp()
        self.image = os.path.join(self.tmp, 'boot', '2026.10.01')
        self.saved = os.path.join(self.tmp, 'accounts')
        os.makedirs(os.path.join(self.image, 'rw', 'etc'))

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(text)

    def test_accounts_are_saved_from_the_overlay(self):
        # Creating a login user at boot copies passwd/group up into rw/etc,
        # whole: that copy is what the running system saw.
        self.write(os.path.join(self.image, 'rw/etc/passwd'), 'frr:x:109:\n')
        self.write(os.path.join(self.image, 'rw/etc/group'), 'frr:x:115:\n')
        with mock.patch.object(image_installer.disk, 'partition_mount') as mount:
            image_installer.save_account_files(self.image, self.saved)
        mount.assert_not_called()
        self.assertEqual(
            image_installer.read_ids(os.path.join(self.saved, 'passwd')), {'frr': 109}
        )
        self.assertEqual(
            image_installer.read_ids(os.path.join(self.saved, 'group')), {'frr': 115}
        )

    def test_accounts_fall_back_to_the_image_squashfs(self):
        def mount(source, path, fstype=''):
            self.assertTrue(source.endswith('2026.10.01.squashfs'))
            self.assertEqual(fstype, 'squashfs')
            self.write(os.path.join(path, 'etc/passwd'), 'frr:x:109:\n')
            self.write(os.path.join(path, 'etc/group'), 'frr:x:115:\n')
            return True

        with mock.patch.object(
            image_installer.disk, 'partition_mount', mount
        ), mock.patch.object(image_installer.disk, 'partition_umount') as umount:
            image_installer.save_account_files(self.image, self.saved)
        umount.assert_called_once()
        self.assertEqual(
            image_installer.read_ids(os.path.join(self.saved, 'passwd')), {'frr': 109}
        )

    def test_each_account_file_comes_from_where_the_system_saw_it(self):
        # Only passwd copied up: the old system saw the upper passwd and the
        # lower group.
        self.write(os.path.join(self.image, 'rw/etc/passwd'), 'svc:x:210:\n')

        def mount(source, path, fstype=''):
            self.write(os.path.join(path, 'etc/passwd'), 'svc:x:109:\n')
            self.write(os.path.join(path, 'etc/group'), 'svc:x:115:\n')
            return True

        with mock.patch.object(image_installer.disk, 'partition_mount', mount), \
                mock.patch.object(image_installer.disk, 'partition_umount') as umount:
            image_installer.save_account_files(self.image, self.saved)
        umount.assert_called_once()
        read = image_installer.read_ids
        self.assertEqual(read(os.path.join(self.saved, 'passwd')), {'svc': 210})
        self.assertEqual(read(os.path.join(self.saved, 'group')), {'svc': 115})

    def test_previous_config_is_copied_with_translated_owners(self):
        prev = os.path.join(self.tmp, 'mnt-config')
        os.mkdir(prev)
        self.write(os.path.join(self.saved, 'passwd'), 'frr:x:109:\n')
        self.write(os.path.join(self.saved, 'group'), 'frr:x:115:\nvyattacfg:x:102:\n')
        new_etc = os.path.join(self.tmp, 'new-etc')
        self.write(os.path.join(new_etc, 'passwd'), 'frr:x:108:\n')
        self.write(os.path.join(new_etc, 'group'), 'frr:x:114:\nvyattacfg:x:103:\n')
        target = os.path.join(self.tmp, 'target')
        with mock.patch.object(
            image_installer, 'DIR_PREVIOUS_CONFIG', prev
        ), mock.patch.object(
            image_installer, 'DIR_PREVIOUS_ACCOUNTS', self.saved
        ), mock.patch.object(
            image_installer, 'DIR_NEW_ACCOUNTS', new_etc
        ), mock.patch.object(
            image_installer, 'DIR_PREVIOUS_SSH', '/nonexistent'
        ), mock.patch.object(
            image_installer, 'copy_config_tree'
        ) as copy_tree:
            image_installer.copy_previous_installation_data(target)
        copy_tree.assert_called_once()
        src, dst, uids, gids, cfg_gid = copy_tree.call_args.args
        self.assertEqual((src, dst), (prev, target + image_installer.DIR_CONFIG))
        self.assertEqual((uids(109), gids(115), cfg_gid), (108, 114, 103))


class TestAddImageFailure(TreeTestCase):
    """What add_image() leaves behind when copying /config fails"""

    def run_add_image(self):
        ii = image_installer
        iso = os.path.join(self.tmp, 'iso')
        rootfs = os.path.join(self.tmp, 'rootfs')
        self.persistence = os.path.join(self.tmp, 'persistence')

        def mount(source, path, fstype='', **kwargs):
            # add_image() creates the mount points itself: fill them as a
            # mount would
            if path == iso:
                open(os.path.join(iso, 'sha256sum.txt'), 'w').close()
            elif path == rootfs:
                os.makedirs(os.path.join(rootfs, 'etc'))
                for name in ('passwd', 'group'):
                    with open(os.path.join(rootfs, 'etc', name), 'w') as f:
                        f.write('vyattacfg:x:102:\n')
            return True

        self.cleanup = mock.Mock()
        failure = PermissionError(1, 'Operation not permitted')
        with mock.patch.multiple(
            ii,
            DIR_ISO_MOUNT=iso,
            DIR_ROOTFS_SRC=rootfs,
            DIR_CONFIG=self.src,
            disk_usage=mock.Mock(return_value=mock.Mock(free=10 * 1024**3)),
            unsaved_commits=mock.Mock(return_value=False),
            image_fetch=mock.Mock(return_value=os.path.join(self.tmp, 'x.iso')),
            validate_compatibility=mock.Mock(),
            run=mock.Mock(return_value=0),
            copy_config_tree=mock.Mock(side_effect=failure),
            cleanup=self.cleanup,
        ), mock.patch.object(
            ii.image, 'is_live_boot', return_value=False
        ), mock.patch.object(
            ii.image, 'get_image_tools_version', return_value=ii.SYSTEM_CFG_VER
        ), mock.patch.object(
            ii.image, 'get_image_version', return_value='new'
        ), mock.patch.object(
            ii.disk, 'partition_mount', mount
        ), mock.patch.object(
            ii.disk, 'partition_umount'
        ), mock.patch.object(
            ii.disk, 'find_persistence', return_value=self.persistence
        ):
            with self.assertRaises(SystemExit):
                ii.add_image.__wrapped__('x.iso', no_prompt=True)

    def removed(self):
        return [
            item
            for call in self.cleanup.call_args_list
            for item in call.kwargs.get('remove_items', [])
        ]

    def test_half_built_image_is_removed(self):
        # Only ENOSPC used to remove it: any other error left boot/<image>
        # behind, and the next 'add system image' failed on mkdir().
        self.run_add_image()
        self.assertIn(os.path.join(self.persistence, 'boot', 'new'), self.removed())

    def test_an_existing_image_is_never_removed(self):
        # With --no-prompt, the name is not checked against installed images.
        existing = os.path.join(self.tmp, 'persistence', 'boot', 'new')
        os.makedirs(os.path.join(existing, 'rw'))
        self.run_add_image()
        self.assertNotIn(existing, self.removed())
        self.assertTrue(os.path.isdir(os.path.join(existing, 'rw')))


class TestCopyOwnershipTraversal(TreeTestCase):
    """copy_ownership(src, dst) gives dst the owner/group/mode of the
    matching src path, walking src. Only paths present in both trees and
    of the same type are touched - these tests cover what must happen to
    the *rest* of a src subtree once its own top-level entry already
    failed that type check.
    """

    def test_destination_symlink_does_not_let_traversal_escape(self):
        # src/X is a real directory; dst/X is a symlink to an unrelated
        # directory outside dst entirely.
        outside = os.path.join(self.tmp, 'outside')
        os.mkdir(outside)
        with open(os.path.join(outside, 'leaf'), 'w') as fh:
            fh.write('x')
        os.chmod(os.path.join(outside, 'leaf'), 0o600)

        os.mkdir(os.path.join(self.src, 'X'))
        with open(os.path.join(self.src, 'X', 'leaf'), 'w') as fh:
            fh.write('x')
        os.chmod(os.path.join(self.src, 'X', 'leaf'), 0o644)

        os.symlink(outside, os.path.join(self.dst, 'X'))

        image_installer.copy_ownership(self.src, self.dst)

        mode = stat.S_IMODE(os.lstat(os.path.join(outside, 'leaf')).st_mode)
        self.assertEqual(
            mode,
            0o600,
            "copy_ownership() followed dst's symlink and modified a file "
            "outside the destination tree",
        )

    def test_destination_regular_file_does_not_crash_traversal(self):
        # src/Y is a real directory; dst/Y is a plain file - descending into
        # src/Y must not then try to lstat() a child path through that file.
        os.mkdir(os.path.join(self.src, 'Y'))
        with open(os.path.join(self.src, 'Y', 'leaf'), 'w') as fh:
            fh.write('x')

        with open(os.path.join(self.dst, 'Y'), 'w') as fh:
            fh.write('not a directory')

        try:
            image_installer.copy_ownership(self.src, self.dst)
        except NotADirectoryError:
            self.fail(
                "copy_ownership() tried to descend into dst/Y, a regular "
                "file, instead of skipping that subtree"
            )


if __name__ == '__main__':
    unittest.main()
