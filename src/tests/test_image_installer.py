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
# Coverage for T9403 (preserve /config ownership across an image upgrade):
# copy_ownership() walks the *source* tree and derives each destination
# path from it. If a source directory's destination counterpart stops
# being a plain directory between copytree() and this pass - swapped for
# a symlink, or never more than a regular file to begin with - the walk
# must stop descending there. Otherwise a symlink lets the chown/chmod
# pass escape outside the target tree, and a plain file makes the next
# lstat() raise NotADirectoryError and abort the upgrade.

import os
import stat
import tempfile
import unittest

from helper import prepare_module

_here = os.path.dirname(__file__)

# get_running_image() falls back to reading directories['data']/version.json
# when it can't find a VyOS-style BOOT_IMAGE kernel argument, which is
# always true on the host these tests run on - point it at a throwaway
# file so importing the module under test doesn't need a real VyOS system.
import vyos.defaults as defaults

_fake_data_dir = tempfile.mkdtemp()
with open(os.path.join(_fake_data_dir, 'version.json'), 'w') as f:
    f.write('{"version": "test"}')
_orig_data_dir = defaults.directories['data']
defaults.directories['data'] = _fake_data_dir + '/'

image_installer = prepare_module(
    os.path.join(_here, '../op_mode/image_installer.py'), 'image_installer')

defaults.directories['data'] = _orig_data_dir


class TestCopyOwnership(unittest.TestCase):
    """copy_ownership(src, dst) gives dst the owner/group/mode of the
    matching src path, walking src. Only paths present in both trees and
    of the same type are touched - these tests cover what must happen to
    the *rest* of a src subtree once its own top-level entry already
    failed that type check.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__('shutil').rmtree(
            self.tmp, ignore_errors=True))
        self.src = os.path.join(self.tmp, 'src')
        self.dst = os.path.join(self.tmp, 'dst')
        os.mkdir(self.src)
        os.mkdir(self.dst)

    def test_destination_symlink_does_not_let_traversal_escape(self):
        # src/X is a real directory; dst/X is a symlink to an unrelated
        # directory outside dst entirely (e.g. left behind if the live
        # /config entry copytree() copied was a symlink at the time, and
        # something replaced it with a real directory before this pass).
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
        # src/Y is a real directory; dst/Y is a plain file (the type the
        # top-level check already rejects) - descending into src/Y must
        # not then try to lstat() a child path through that file.
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
