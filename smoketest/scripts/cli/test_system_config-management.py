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
import pwd
import tempfile
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.config_mgmt import ConfigMgmt
from vyos.config_mgmt import commit_hooks
from vyos.config_mgmt import commit_post_hook_dir
from vyos.utils.process import cmdl

base_path = ['system', 'config-management']
archive_base = base_path + ['commit-archive', 'location']

archive_hook = os.path.join(commit_post_hook_dir, commit_hooks['commit_archive'])
archive_vrf = 'ARCHIVE'


class TestSystemConfigManagement(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSystemConfigManagement, cls).setUpClass()
        # ensure we can also run this test on a live system - clean out any
        # existing commit-archive configuration first
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_delete(['vrf', 'name', archive_vrf])
        self.cli_commit()
        super().tearDown()

    def test_01_commit_archive(self):
        # The plain transports (scp/sftp/ssh/ftp/ftps/http/https/tftp) share the
        # same URL builder, so a representative subset covers every branch:
        # full auth+port+path, a bare server (no auth, default path), the
        # git-specific 'git+<transport>' scheme with default and explicit
        # transport, and an IPv6 literal. Each entry lists the set commands plus
        # the URL it must produce
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
            # ftp with a password but no username -> ':password@' (ftp falls
            # back to anonymous/REMOTE_USERNAME for the user)
            'ftp-passonly': (
                [
                    ['ftp', 'authentication', 'password', 's3cr3t'],
                    ['ftp', 'server', '192.0.2.1'],
                ],
                'ftp://:s3cr3t@192.0.2.1/',
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
            # IPv6 server literal -> bracketed in the netloc
            'scp-ipv6': (
                [
                    ['scp', 'authentication', 'username', 'bob'],
                    ['scp', 'server', '2001:db8::1'],
                    ['scp', 'port', '22'],
                    ['scp', 'path', '/backups'],
                ],
                'scp://bob@[2001:db8::1]:22/backups',
            ),
            # git to a local repository: file transport, path, no server
            'git-file': (
                [['git', 'transport', 'file'], ['git', 'path', '/srv/configs.git']],
                'git+file:///srv/configs.git',
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
        location = archive_base + ['archive']

        # two transport protocols on one location -> rejected
        self.cli_set(location + ['scp', 'path', '/a'])
        self.cli_set(location + ['ftp', 'path', '/b'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # one protocol now, but it has no server -> rejected
        self.cli_delete(location + ['ftp'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # server set, but a password without a username -> rejected
        self.cli_set(location + ['scp', 'server', '192.0.2.1'])
        self.cli_set(location + ['scp', 'authentication', 'password', 'p'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # add the username -> should commit
        self.cli_set(location + ['scp', 'authentication', 'username', 'u'])
        self.cli_commit()

        # a valid location was committed, so the archive hook is installed
        self.assertTrue(os.path.islink(archive_hook))

    def test_03_git_file_verify(self):
        # git over file:// is a local repository: it needs a path and must not
        # carry remote-only nodes (server/port/authentication)
        location = archive_base + ['local']

        # file transport without a path -> rejected
        self.cli_set(location + ['git', 'transport', 'file'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(location + ['git', 'path', '/srv/configs.git'])

        # each remote-only node is meaningless for a local repository
        for node in (
            ['server', '192.0.2.1'],
            ['port', '22'],
            ['authentication', 'username', 'u'],
        ):
            self.cli_set(location + ['git'] + node)
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_delete(location + ['git', node[0]])

        # path only -> commits
        self.cli_commit()
        self.assertTrue(os.path.islink(archive_hook))

    def test_04_git_archive_vrf(self):
        # T9619: archiving to git in a VRF failed when not run as root.
        # Use a local repository, so no network is needed.
        tmp = tempfile.TemporaryDirectory(prefix='smoketest-archive-')
        self.addCleanup(tmp.cleanup)
        repo = os.path.join(tmp.name, 'repo.git')
        work = os.path.join(tmp.name, 'work')
        # git needs an author name and email to create the first commit
        git_env = {
            **os.environ,
            'GIT_AUTHOR_NAME': 'smoketest',
            'GIT_AUTHOR_EMAIL': 'smoketest@vyos',
            'GIT_COMMITTER_NAME': 'smoketest',
            'GIT_COMMITTER_EMAIL': 'smoketest@vyos',
        }

        # create the repository; it needs one commit before we can push to it
        cmdl(['git', 'init', '--bare', '--initial-branch=main', repo])
        cmdl(['git', 'clone', repo, work])
        cmdl(['git', '-C', work, 'commit', '--allow-empty', '-m', 'init'], env=git_env)
        cmdl(['git', '-C', work, 'push', 'origin', 'HEAD:main'])

        self.cli_set(['vrf', 'name', archive_vrf, 'table', '1050'])
        self.cli_set(base_path + ['commit-archive', 'vrf', archive_vrf])
        self.cli_set(archive_base + ['local', 'git', 'transport', 'file'])
        self.cli_set(archive_base + ['local', 'git', 'path', repo])
        self.cli_commit()

        # run the archive hook, the test fails if the hook fails
        cmdl([archive_hook])

        # the commit author must be our user, not root
        author = cmdl(['git', '--git-dir', repo, 'log', '-1', '--format=%ae'])
        user = pwd.getpwuid(os.getuid()).pw_name
        self.assertTrue(author.startswith(f'{user}@'))
        # the commit must contain the saved config
        files = cmdl(
            ['git', '--git-dir', repo, 'show', '--name-only', '--format=', 'HEAD']
        )
        self.assertIn('config.boot-', files)


if __name__ == '__main__':
    unittest.main(verbosity=2)
