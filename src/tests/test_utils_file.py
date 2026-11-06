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
import stat
import tempfile
import unittest
from unittest import mock

from pathlib import Path

import vyos.utils.file
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


class _SpyFile:
    """Proxy around a file object that records perms on each write."""

    def __init__(self, fh, log):
        self._fh = fh
        self._log = log

    def write(self, data):
        self._log.append(stat.S_IMODE(os.fstat(self._fh.fileno()).st_mode))
        return self._fh.write(data)

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def __enter__(self):
        self._fh.__enter__()
        return self

    def __exit__(self, *exc):
        return self._fh.__exit__(*exc)

    def __getattr__(self, name):
        return getattr(self._fh, name)


EXPECTED_MODE = 0o600


class TestWriteFilePermissions(unittest.TestCase):
    def setUp(self):
        # pylint: disable=consider-using-with
        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, 'dummy.txt')
        # Set umask so default perms are known.
        self._old_umask = os.umask(0o022)

    def tearDown(self):
        os.umask(self._old_umask)
        self._tmp.cleanup()

    def test_permissions_at_write(self):
        real_open = open
        modes_at_write = []

        def spy_open(file, *args, **kwargs):
            # pylint: disable=consider-using-with
            fh = real_open(file, *args, **kwargs)
            if os.fspath(file) == self.path:
                return _SpyFile(fh, modes_at_write)
            return fh

        with mock.patch.object(
            vyos.utils.file, 'open', side_effect=spy_open, create=True
        ) as mock_open:
            vyos.utils.file.write_file(self.path, 'secret data', mode=EXPECTED_MODE)

        mock_open.assert_called()
        self.assertTrue(modes_at_write, 'write() was not called')
        self.assertEqual(
            modes_at_write[0],
            EXPECTED_MODE,
            f'first write happened with mode {oct(modes_at_write[0])}, expected {oct(EXPECTED_MODE)}',
        )
