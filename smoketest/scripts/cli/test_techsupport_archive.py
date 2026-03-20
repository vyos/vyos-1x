#!/usr/bin/env python3
#
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

import io
import re
import contextlib
import pathlib
import tarfile
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.utils.process import call
from vyos.utils.file import get_name_from_path

base_path = ['generate tech-support archive']
testdir = pathlib.Path('/tmp/_test_techsupport_archive')


def tar_gz_paths(archive_path: pathlib.Path, max_depth: int = 5) -> set:
    """
    Return all member paths inside `archive_path`.

    Nested archives are expanded recursively and represented as:
      "inner.tar.gz::path/inside/inner"
    """

    def is_nested(name: str) -> bool:
        nested_suffixes = ('.tar.gz', '.tgz', '.tar')
        return name.lower().endswith(nested_suffixes)

    out = set()

    def walk_bytes(data: bytes, prefix: str, depth: int):
        if depth > max_depth:
            return

        bio = io.BytesIO(data)
        with tarfile.open(fileobj=bio, mode='r:*') as tf:
            for member in tf.getmembers():
                out.add(f'{prefix}::{member.name}' if prefix else member.name)

                if member.isreg() and is_nested(member.name) and depth < max_depth:
                    file = tf.extractfile(member)
                    if file is None:
                        continue

                    sub_prefix = f'{prefix}::{member.name}' if prefix else member.name
                    walk_bytes(file.read(), sub_prefix, depth + 1)

    walk_bytes(archive_path.read_bytes(), prefix='', depth=0)

    return out


@contextlib.contextmanager
def stub_files(file_paths: list[str]):
    """
    Context manager for tests.

    Creates a temporary set of files and removes it after use.
    Example:
        with stub_files(['a.txt', 'dir/b.txt']):
            pass
    """

    paths = [pathlib.Path(file_path) for file_path in file_paths]

    try:
        for path in paths:
            if path.parent.exists():
                path.touch()

        yield

    finally:
        for path in paths:
            path.unlink(missing_ok=True)


class TestTechSupportArchive(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        # always forward to base class
        super().tearDown()

        if testdir.exists():
            call(f'sudo rm -rf {testdir}')

    def _check_path(self, path: str | pathlib.Path, state: bool, err_message: str):
        if isinstance(path, str):
            path = pathlib.Path(path)

        if state:
            self.assertTrue(path.exists(), err_message)
        else:
            self.assertFalse(path.exists(), err_message)

    def _extract_archive_path(self, output: str) -> pathlib.Path:
        match = re.search(r'located in ([^\s]+\.tar\.gz)', output)
        path = match.group(1) if match else None

        err_message = (
            'It is not possible to extract the path to the resulting '
            'archive from stdout:'
            f'\n```\n{output}\n```'
        )
        assert path is not None, err_message

        return pathlib.Path(path)

    def _extract_archive_inner_path_prefix(self, archive_path: pathlib.Path):
        # Convert
        #   `bdbdd9a4807f_tech-support-archive_2026-02-02T15-33-26.tar.gz`
        # to
        #   `bdbdd9a4807f_tech-support-archive_2026-02-02T15-33-26`

        return get_name_from_path(archive_path)

    def assertPathExists(self, path: str):
        err_message = f'Path `{path}` does not exist after generating a archive'
        self._check_path(path, True, err_message)

    def assertNotPathExists(self, path: str):
        err_message = f'Path `{path}` still exists after generating a archive'
        self._check_path(path, False, err_message)

    def assertExpectedArcPaths(
        self, archive_path: pathlib.Path, expected_paths: list[str]
    ):
        actual = tar_gz_paths(archive_path)
        expected = frozenset(expected_paths)

        missing = sorted(expected - actual)

        if missing:
            lines = [f'Archive paths mismatch: {archive_path}', 'Missing:']
            lines += [f'  - {p}' for p in missing]
            raise AssertionError('\n'.join(lines))

    def assertNotExpectedArcPaths(
        self, archive_path: pathlib.Path, unexpected_paths: list[str]
    ):
        actual = tar_gz_paths(archive_path)
        unexpected = frozenset(unexpected_paths)

        extra = sorted(actual & unexpected)

        if extra:
            lines = [f'Archive paths mismatch: {archive_path}', 'Unexpected:']
            lines += [f'  - {p}' for p in extra]
            raise AssertionError('\n'.join(lines))

    def test_general_archive_structure(self):
        output = self.op_mode(base_path)

        archive_path = self._extract_archive_path(output)
        self.assertPathExists(archive_path)
        self.assertEqual(str(archive_path.parent), '/tmp')

        prefix = self._extract_archive_inner_path_prefix(archive_path)
        self.assertExpectedArcPaths(
            archive_path,
            [
                f'{prefix}/show_tech-support_report/vyos-main-info',
                f'{prefix}/config.tar.gz::opt/vyatta/etc/config/config.boot',
                f'{prefix}/core-dump.tar.gz::var/core',
                f'{prefix}/home.tar.gz::home/vyos/.profile',
                f'{prefix}/root.tar.gz::root/.profile',
                f'{prefix}/run.tar.gz::run',
                f'{prefix}/tmp.tar.gz::tmp/vyos-config-status',
                f'{prefix}/topology-logical.png',
                f'{prefix}/topology.png',
                f'{prefix}/var-log.tar.gz::var/log/journal',
            ],
        )

        if archive_path.exists():
            call(f'sudo rm -f {archive_path}')

    def test_excluded_archive_files(self):
        fake_files = [
            '/opt/vyatta/etc/config/_test_fake_vyos.iso',
            '/home/vyos/_test_fake_vyos.iso',
            '/tmp/_test_fake_vyos.iso',
            '/opt/vyatta/etc/config/_test_fake_archive.tar.gz',
            '/home/vyos/_test_fake_archive.tar.gz',
            '/tmp/_test_fake_archive.tar.gz',
            '/home/vyos/drops-debug_9999-12-31T23-59-59',
            '/home/vyos/ffffffffffff_tech-support-archive_9999-12-31T23-59-59',
            '/tmp/drops-debug_9999-12-31T23-59-59',
            '/tmp/ffffffffffff_tech-support-archive_9999-12-31T23-59-59',
        ]
        with stub_files(fake_files):
            output = self.op_mode(base_path)

        archive_path = self._extract_archive_path(output)
        self.assertPathExists(archive_path)

        prefix = self._extract_archive_inner_path_prefix(archive_path)
        self.assertNotExpectedArcPaths(
            archive_path,
            [
                f'{prefix}/config.tar.gz::opt/vyatta/etc/config/_test_fake_vyos.iso',
                f'{prefix}/home.tar.gz::home/vyos/_test_fake_vyos.iso',
                f'{prefix}/tmp.tar.gz::tmp/_test_fake_vyos.iso',
                f'{prefix}/var.tar.gz::var/log/messages',
                f'{prefix}/var.tar.gz::var/log/messages.1',
                f'{prefix}/config.tar.gz::opt/vyatta/etc/config/_test_fake_archive.tar.gz',
                f'{prefix}/home.tar.gz::home/vyos/_test_fake_archive.tar.gz',
                f'{prefix}/tmp.tar.gz::tmp/_test_fake_archive.tar.gz',
                f'{prefix}/home.tar.gz::home/vyos/drops-debug_9999-12-31T23-59-59',
                f'{prefix}/home.tar.gz::home/vyos/ffffffffffff_tech-support-archive_9999-12-31T23-59-59',
                f'{prefix}/tmp.tar.gz::tmp/drops-debug_9999-12-31T23-59-59',
                f'{prefix}/tmp.tar.gz::tmp/ffffffffffff_tech-support-archive_9999-12-31T23-59-59',
            ],
        )

        if archive_path.exists():
            call(f'sudo rm -f {archive_path}')

    def test_custom_archive_path(self):
        output = self.op_mode(base_path + [str(testdir / 'foo')])

        archive_path = self._extract_archive_path(output)
        self.assertPathExists(archive_path)
        self.assertEqual(archive_path.parent, testdir)
        self.assertEqual(archive_path.name, 'foo.tar.gz')

    def test_custom_directory_archive_path(self):
        output = self.op_mode(base_path + [str(testdir) + '/bar/'])

        archive_path = self._extract_archive_path(output)
        self.assertPathExists(archive_path)
        self.assertEqual(archive_path.parent.name, 'bar')
        self.assertEqual(archive_path.suffix, '.gz')


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
