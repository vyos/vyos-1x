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

import tempfile
import unittest

from pathlib import Path

from vyos.utils.file import copy_recursive
from vyos.utils.file import move_recursive


class TestVyOSUtilsFile(unittest.TestCase):
    def setUp(self):
        """Create temporary directories for source and destination."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.src = Path(self.tmpdir.name) / 'src'
        self.dst = Path(self.tmpdir.name) / 'dst'

        # Create test directory structure in `src`
        (self.src / 'subdir').mkdir(parents=True)
        (self.dst).mkdir(parents=True)

        # Create files
        (self.src / 'file1.txt').write_text('hello world')
        (self.src / 'subdir' / 'file2.txt').write_text('subdir file')

    def tearDown(self):
        """Cleanup temp directory."""
        self.tmpdir.cleanup()

    def test_copy_recursive_no_overwrite(self):
        copy_recursive(str(self.src), str(self.dst), overwrite=False)

        self.assertTrue((self.dst / 'file1.txt').exists())
        self.assertTrue((self.dst / 'subdir' / 'file2.txt').exists())

    def test_copy_recursive_skip_existing(self):
        # Create conflicting file in destination
        (self.dst / 'file1.txt').write_text('different content')

        copy_recursive(str(self.src), str(self.dst), overwrite=False)

        # Destination should remain the same (not overwritten)
        content = (self.dst / 'file1.txt').read_text()
        self.assertEqual(content, 'different content')

    def test_copy_recursive_overwrite(self):
        (self.dst / 'file1.txt').write_text('different content')

        copy_recursive(str(self.src), str(self.dst), overwrite=True)

        # Destination should be overwritten with source content
        content = (self.dst / 'file1.txt').read_text()
        self.assertEqual(content, 'hello world')

    def test_move_recursive(self):
        move_recursive(str(self.src), str(self.dst), overwrite=False)

        # Files should appear in destination
        self.assertTrue((self.dst / 'file1.txt').exists())
        self.assertTrue((self.dst / 'subdir' / 'file2.txt').exists())

        # Source should be removed
        self.assertFalse(self.src.exists())

    def test_move_recursive_overwrite(self):
        # Prepare conflicting file in destination
        (self.dst / 'file1.txt').write_text('conflicting')

        move_recursive(str(self.src), str(self.dst), overwrite=True)

        content = (self.dst / 'file1.txt').read_text()
        self.assertEqual(content, 'hello world')  # overwritten
        self.assertFalse(self.src.exists())  # source cleaned up
