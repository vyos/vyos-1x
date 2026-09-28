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
#
# A configuration session is a kernel overlayfs mount. The active
# configuration is the read-only lower layer, shared by every session; each
# session gets a private upper layer holding its uncommitted edits, a private
# kernel work directory, and a merged mount point the CLI reads and writes.
#
# Committing swaps that shared lower layer for a newly built one, then
# re-points every other live session at it. This is the only place one
# session reaches into another, and the kernel offers no protection here:
# altering a layer beneath a mounted overlay is undefined. When it goes wrong
# nothing raises an error - a session reads a stale or half-written
# configuration, and its next commit writes that back to disk, silently
# reverting somebody else's work.
#
# Four sessions are held open at once, each tied to a real login shell, which
# is what the backend keys a session to; invented identifiers get reaped as
# debris. The tests assert the mount layout is what it claims to be,
# uncommitted edits stay private, a commit reaches everyone else without
# destroying their pending work or reverting an earlier one, discarding
# restores the active configuration rather than emptying it, and no mounts or
# scratch directories survive teardown.
#
# Nothing else in the suite opens more than one session.

import os
import re
import unittest

from subprocess import Popen
from subprocess import PIPE
from subprocess import STDOUT
from subprocess import DEVNULL
from threading import Thread
from time import sleep

from vyos.configsession import inject_vyos_env

CLI_SHELL_API = '/bin/cli-shell-api'
SBIN = '/opt/vyatta/sbin'

base_path = ['system', 'static-host-mapping', 'host-name']

# Number of concurrent configuration sessions to hold open. Four is enough to
# have one committing while the others are mid edit.
n_sessions = 4

host_prefix = 'smoketest-ovl'
config_dir = '/opt/vyatta/config'
session_dir = f'{config_dir}/tmp'
ovl_work_dir = f'{config_dir}/ovl_work'


class SessionError(Exception):
    pass


class CliSession:
    """A single configuration session, driven the way an independent login
    shell drives one.

    Deliberately not built on vyos.configsession.ConfigSession: that class
    assigns ``session_env = os.environ`` by reference, so every ConfigSession
    object in a process ends up sharing - and fighting over - one environment.
    That is harmless when a process owns a single session, which is the
    documented usage, but it makes several concurrent sessions impossible to
    express. Here each session keeps its own environment dictionary and never
    touches os.environ.
    """

    shell = None

    def __init__(self):
        # The session ID must be the PID of a live 'vbash'. setupSession()
        # reaps any session directory owned by the same non-root user whose
        # ID does not belong to a running vbash - that is how it cleans up
        # after a shell that died without leaving config mode. Inventing IDs
        # would make each new session delete all the previous ones, so hold a
        # real shell open per session, exactly as a logged in operator does.
        self.shell = Popen(
            ['/bin/vbash', '-c', 'read -r _'], stdin=PIPE, stdout=DEVNULL, stderr=DEVNULL
        )
        self.sid = str(self.shell.pid)
        out = self._raw([CLI_SHELL_API, 'getSessionEnv', self.sid], os.environ)
        self.env = inject_vyos_env(dict(os.environ))
        for k, v in re.findall(r'([A-Z_]+)=([^;\s]+)', out):
            self.env[k] = v
        self.env['SESSION_PID'] = self.sid
        self.run([CLI_SHELL_API, 'setupSession'])

    @staticmethod
    def _raw(cmd, env):
        p = Popen(cmd, stdout=PIPE, stderr=STDOUT, env=env)
        out, _ = p.communicate()
        out = out.decode()
        if p.returncode != 0:
            raise SessionError(f'{" ".join(cmd)} failed: {out}')
        return out

    def run(self, cmd):
        return self._raw(cmd, self.env)

    def set(self, path, value=None):
        cmd = [f'{SBIN}/my_set'] + path
        if value is not None:
            cmd.append(value)
        return self.run(cmd)

    def delete(self, path):
        return self.run([f'{SBIN}/my_delete'] + path)

    def discard(self):
        return self.run([f'{SBIN}/my_discard'])

    def commit(self, retries=60):
        # A sibling holding the global commit lock is expected, not an error.
        last = None
        for _ in range(retries):
            try:
                return self.run([f'{SBIN}/my_commit'])
            except SessionError as e:
                last = e
                if 'locked' not in str(e).lower():
                    raise
                sleep(0.5)
        raise SessionError(f'commit never acquired the lock: {last}')

    def show(self):
        """Working configuration: the merged overlay view."""
        return self.run([CLI_SHELL_API, 'showConfig'])

    def show_active(self):
        """Active configuration only: the overlay lower layer."""
        return self.run(
            [CLI_SHELL_API, '--show-active-only', '--show-ignore-edit', 'showConfig']
        )

    def teardown(self):
        try:
            return self.run([CLI_SHELL_API, 'teardownSession'])
        finally:
            self.close()

    def close(self):
        if self.shell is not None and self.shell.poll() is None:
            try:
                self.shell.stdin.write(b'\n')
                self.shell.stdin.flush()
            except (BrokenPipeError, ValueError):
                pass
            try:
                self.shell.wait(timeout=5)
            except Exception:
                self.shell.kill()
                self.shell.wait()
        if self.shell is not None and self.shell.stdin is not None:
            try:
                self.shell.stdin.close()
            except (BrokenPipeError, ValueError):
                pass


def overlay_mounts() -> list:
    """Session working directories currently mounted as overlayfs."""
    found = []
    with open('/proc/self/mountinfo') as f:
        for line in f:
            fields = line.split()
            try:
                sep = fields.index('-')
            except ValueError:
                continue
            mount_point = fields[4]
            if fields[sep + 1] == 'overlay' and mount_point.startswith(
                f'{session_dir}/new_config_'
            ):
                found.append(mount_point)
    return found


class TestConfigSessionConcurrent(unittest.TestCase):
    def setUp(self):
        self.sessions = [CliSession() for _ in range(n_sessions)]
        self._ids = [s.sid for s in self.sessions]

    def tearDown(self):
        # Drop pending changes first so the cleanup commit only removes what
        # the test actually committed.
        for session in self.sessions:
            try:
                session.discard()
            except SessionError:
                pass

        if self.sessions:
            cleanup = self.sessions[0]
            try:
                active = cleanup.show_active()
                removed = False
                for i in range(n_sessions):
                    if f'{host_prefix}-{i}' in active:
                        cleanup.delete(base_path + [f'{host_prefix}-{i}'])
                        removed = True
                if removed:
                    cleanup.commit()
            except SessionError:
                pass

        for session in self.sessions:
            try:
                session.teardown()
            except SessionError:
                session.close()
        self.sessions = []

    def test_session_mounts_are_overlayfs(self):
        # Every open session must be backed by its own overlay mount, with its
        # own upper layer and its own overlayfs workdir.
        mounts = overlay_mounts()
        for sid in self._ids:
            self.assertIn(f'{session_dir}/new_config_{sid}', mounts)
            self.assertTrue(
                os.path.isdir(f'{ovl_work_dir}/{sid}'),
                msg=f'no overlayfs workdir for session {sid}',
            )
            self.assertTrue(os.path.isdir(f'{session_dir}/changes_only_{sid}'))

    def test_commit_is_visible_to_other_sessions(self):
        # Every session stages a change of its own, before anybody commits.
        for i, session in enumerate(self.sessions):
            session.set(base_path + [f'{host_prefix}-{i}', 'inet'], f'10.91.0.{i + 1}')

        # Commit them one at a time. After each commit the sessions that have
        # not committed yet must see two things at once: the node somebody
        # else just committed, and their own edit still pending. The first
        # proves the session was moved onto the new active configuration, the
        # second proves its own upper layer survived that move.
        for i, session in enumerate(self.sessions):
            session.commit()

            for j, other in enumerate(self.sessions):
                config = other.show()
                for committed in range(i + 1):
                    self.assertIn(
                        f'{host_prefix}-{committed} ',
                        config,
                        msg=f'session {j} cannot see commit from session {committed}',
                    )
                if j > i:
                    self.assertIn(
                        f'{host_prefix}-{j} ',
                        config,
                        msg=f'session {j} lost its own pending change',
                    )

    def test_commit_does_not_revert_a_sibling(self):
        # The regression this guards against: session B holds a mount over the
        # old active configuration, A commits, and B's commit then writes B's
        # stale view back, silently reverting A.
        a, b = self.sessions[0], self.sessions[1]

        a.set(base_path + [f'{host_prefix}-0', 'inet'], '10.91.1.1')
        a.commit()

        b.set(base_path + [f'{host_prefix}-1', 'inet'], '10.91.1.2')
        b.commit()

        for session in (a, b):
            active = session.show_active()
            self.assertIn(f'{host_prefix}-0 ', active)
            self.assertIn(f'{host_prefix}-1 ', active)

    def test_discard_restores_active_config(self):
        # Discarding clears the session's upper layer. Done wrongly - by
        # deleting through the merged mount - it would write whiteouts and
        # leave the session seeing an empty configuration rather than the
        # active one.
        session = self.sessions[0]
        session.set(base_path + [f'{host_prefix}-0', 'inet'], '10.91.2.1')
        session.commit()

        session.set(base_path + [f'{host_prefix}-1', 'inet'], '10.91.2.2')
        self.assertIn(f'{host_prefix}-1 ', session.show())

        session.discard()

        config = session.show()
        # the committed node must still be there ...
        self.assertIn(f'{host_prefix}-0 ', config)
        # ... and the discarded one must be gone
        self.assertNotIn(f'{host_prefix}-1 ', config)

        # the session must remain usable afterwards
        session.set(base_path + [f'{host_prefix}-2', 'inet'], '10.91.2.3')
        session.commit()
        self.assertIn(f'{host_prefix}-2 ', session.show_active())

    def test_parallel_commits(self):
        # Drive every session at once. The commit lock serialises the commits
        # themselves, so what this exercises is the re-stacking that follows
        # each commit happening while the other sessions are actively in use.
        errors = []

        def worker(idx, session):
            try:
                for round_ in range(3):
                    session.set(
                        base_path + [f'{host_prefix}-{idx}', 'inet'],
                        f'10.92.{round_}.{idx + 1}',
                    )
                    session.commit()
            except Exception as e:  # noqa: BLE001 - collected and reported below
                errors.append(f'session {idx}: {e}')

        threads = [
            Thread(target=worker, args=(i, s)) for i, s in enumerate(self.sessions)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], msg='\n'.join(errors))

        # Every session's writes must have survived every other session's
        # commits.
        active = self.sessions[0].show_active()
        for i in range(n_sessions):
            self.assertIn(f'{host_prefix}-{i} ', active)
            self.assertIn(f'10.92.2.{i + 1}', active)

    def test_no_mount_or_workdir_leak(self):
        before = set(overlay_mounts())
        for sid in self._ids:
            self.assertIn(f'{session_dir}/new_config_{sid}', before)

        ids = list(self._ids)
        for session in self.sessions:
            session.teardown()
        self.sessions = []

        after = set(overlay_mounts())
        for sid in ids:
            self.assertNotIn(
                f'{session_dir}/new_config_{sid}',
                after,
                msg=f'session {sid} left its overlay mounted',
            )
            self.assertFalse(
                os.path.exists(f'{ovl_work_dir}/{sid}'),
                msg=f'session {sid} left its overlayfs workdir behind',
            )
            self.assertFalse(
                os.path.exists(f'{session_dir}/new_config_{sid}'),
                msg=f'session {sid} left its working directory behind',
            )


if __name__ == '__main__':
    unittest.main(verbosity=2)
