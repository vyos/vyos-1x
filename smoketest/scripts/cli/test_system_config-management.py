#!/usr/bin/env python3
#
# Copyright (C) VyOS Inc.
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
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.config_mgmt import ConfigMgmt
from vyos.config_mgmt import commit_hooks
from vyos.config_mgmt import commit_post_hook_dir

base_path = ['system', 'config-management']
archive_base = base_path + ['commit-archive', 'location']

archive_hook = os.path.join(commit_post_hook_dir, commit_hooks['commit_archive'])


class TestSystemConfigManagement(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSystemConfigManagement, cls).setUpClass()
        # ensure we can also run this test on a live system - clean out any
        # existing commit-archive configuration first
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()
        super().tearDown()

    def test_01_commit_archive(self):
        # The plain transports (scp/sftp/ssh/ftp/ftps/http/https/tftp) share the
        # same URL builder, so a representative subset covers every branch:
        # full auth+port+path, a bare server (no auth, default path), and the
        # git-specific 'git+<transport>' scheme with default and explicit
        # transport. Each entry lists the set commands plus the URL it must produce
        locations = {
            # auth + port + explicit path
            'scp-dest': (
                [
                    ['scp', 'authentication', 'username', 'bob'],
                    ['scp', 'authentication', 'password', 's3cr3t'],
                    ['scp', 'server', '192.0.2.1'],
                    ['scp', 'port', '2222'],
                    ['scp', 'path', '/backups'],
                ],
                'scp://bob:s3cr3t@192.0.2.1:2222/backups',
            ),
            # no auth, no port, default path
            'tftp-dest': (
                [['tftp', 'server', '192.0.2.8']],
                'tftp://192.0.2.8/',
            ),
            # git, no transport -> defaults to git+https
            'git-dest': (
                [
                    ['git', 'authentication', 'username', 'git'],
                    ['git', 'authentication', 'password', 'token'],
                    ['git', 'server', 'git.example.com'],
                    ['git', 'path', '/repo.git'],
                ],
                'git+https://git:token@git.example.com/repo.git',
            ),
            # git with an explicit transport
            'git-ssh-dest': (
                [['git', 'transport', 'ssh'], ['git', 'server', 'git.example.com']],
                'git+ssh://git.example.com/',
            ),
        }

        for name, (options, _) in locations.items():
            for option in options:
                self.cli_set(archive_base + [name] + option)

        self.cli_commit()

        # a configured commit-archive installs the post-commit hook
        self.assertTrue(os.path.islink(archive_hook))

        # check that the URLs are built correctly
        mgmt = ConfigMgmt()
        for name, (_, expected_url) in locations.items():
            for proto, conf in mgmt.locations[name].items():
                url = ConfigMgmt._build_archive_url(proto, conf)
                self.assertEqual(url, expected_url)

        # removing all locations removes the hook again
        self.cli_delete(archive_base)
        self.cli_commit()
        self.assertFalse(os.path.islink(archive_hook))

    def test_02_commit_archive_verify(self):
        # A location with more than one transport protocol is rejected.
        self.cli_set(archive_base + ['multi', 'scp', 'server', '192.0.2.1'])
        self.cli_set(archive_base + ['multi', 'ftp', 'server', '192.0.2.2'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(archive_base + ['multi'])

        # A transport protocol without a server is rejected.
        self.cli_set(archive_base + ['no-server', 'scp', 'path', '/x'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(archive_base + ['no-server'])

        # authentication requires both username and password.
        self.cli_set(archive_base + ['half-auth', 'ftp', 'server', '192.0.2.3'])
        self.cli_set(
            archive_base + ['half-auth', 'ftp', 'authentication', 'username', 'u']
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # supplying the missing password makes it valid and it commits
        self.cli_set(
            archive_base + ['half-auth', 'ftp', 'authentication', 'password', 'p']
        )
        self.cli_commit()

        # a valid location was committed, so the archive hook is installed
        self.assertTrue(os.path.islink(archive_hook))


if __name__ == '__main__':
    unittest.main(verbosity=2)
