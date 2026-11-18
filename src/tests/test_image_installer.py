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
                os.path.join(_here, '../op_mode/image_installer.py'),
                'image_installer')
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
            mode, 0o600,
            "copy_ownership() followed dst's symlink and modified a file "
            "outside the destination tree")

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
                "file, instead of skipping that subtree")


if __name__ == '__main__':
    unittest.main()
