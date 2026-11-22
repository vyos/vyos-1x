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
# Committing swaps that shared lower layer for a newly built one. Other
# sessions are deliberately left where they are: unmounting a session from
# outside can lose a change that is being written into it at that moment. A
# session moves onto the new active configuration by itself, with its next
# operation, once nothing else is working on it; a commit and a load insist
# on it. When this goes wrong nothing
# raises an error - a session commits a stale view, silently reverting
# somebody else's work, or a change it reported as made is gone.
#
# Four sessions are held open at once, each tied to a real login shell, which
# is what the backend keys a session to; invented identifiers get reaped as
# debris. The tests assert the mount layout is what it claims to be,
# uncommitted edits stay private, other sessions follow a commit without
# losing their pending work or reverting it, discarding
# restores the active configuration rather than emptying it, and no mounts or
# scratch directories survive teardown.
#
# The mounts are made by a privileged helper, while the directories it works
# in are writable by the whole configuration group. The remaining tests plant
# what a group member could, and assert the helper refuses to follow it.
#
# Nothing else in the suite opens more than one session.

import os
import re
import resource
import shutil
import stat
import unittest

from subprocess import Popen
from subprocess import call
from subprocess import PIPE
from subprocess import STDOUT
from subprocess import DEVNULL
from tempfile import mkdtemp
from threading import Thread
from time import sleep

from vyos.configsession import inject_vyos_env

CLI_SHELL_API = '/bin/cli-shell-api'
SBIN = '/opt/vyatta/sbin'
OVL_HELPER = f'{SBIN}/vyos-cfg-overlay-helper'

base_path = ['system', 'static-host-mapping', 'host-name']

# Number of concurrent configuration sessions to hold open. Four is enough to
# have one committing while the others are mid edit.
n_sessions = 4

host_prefix = 'smoketest-ovl'
config_dir = '/opt/vyatta/config'
session_dir = f'{config_dir}/tmp'
ovl_work_dir = f'{config_dir}/ovl_work'

# A well-formed session ID no process can have, for planted sessions.
bogus_sid = '9999999999'
planted_mnt = f'{session_dir}/new_config_{bogus_sid}'
planted_upper = f'{session_dir}/changes_only_{bogus_sid}'


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


def overlay_mounts() -> dict:
    """Session working directories currently mounted as overlayfs, mapped to
    their per-mount options."""
    found = {}
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
                found[mount_point] = fields[5]
    return found


def mount_id(path):
    """Mount ID of the topmost mount at path, or None."""
    found = None
    with open('/proc/self/mountinfo') as f:
        for line in f:
            fields = line.split()
            if fields[4] == path:
                found = fields[0]
    return found


def old_active_trees():
    """Superseded active configurations still kept around."""
    return [n for n in os.listdir(config_dir) if n.startswith('active.new.')]


def mount_fstype(path):
    """Filesystem type of the topmost mount at path, or None."""
    fstype = None
    with open('/proc/self/mountinfo') as f:
        for line in f:
            fields = line.split()
            if fields[4] == path:
                fstype = fields[fields.index('-') + 1]
    return fstype


def remove_planted():
    if planted_mnt in overlay_mounts():
        call([OVL_HELPER, 'umount', bogus_sid], stdout=DEVNULL, stderr=DEVNULL)
    for path in (planted_mnt, planted_upper):
        if os.path.islink(path):
            os.unlink(path)
        elif os.path.isdir(path):
            os.rmdir(path)
    shutil.rmtree(f'{ovl_work_dir}/{bogus_sid}', ignore_errors=True)


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
            # nothing in a configuration tree is a device or set-user-ID
            options = mounts[f'{session_dir}/new_config_{sid}'].split(',')
            self.assertIn('nosuid', options)
            self.assertIn('nodev', options)

    def test_commit_is_visible_to_other_sessions(self):
        # Every session stages a change of its own, before anybody commits.
        for i, session in enumerate(self.sessions):
            session.set(base_path + [f'{host_prefix}-{i}', 'inet'], f'10.91.0.{i + 1}')

        # Commit them one at a time. After each commit the sessions that have
        # not committed yet must see two things at once: the node somebody
        # else just committed, and their own edit still pending. The first
        # proves the session moved onto the new active configuration, the
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

    def test_planted_session_is_left_alone(self):
        # A planted session whose mount point is a symlink to some other mount
        # must never get that mount touched, and must not keep superseded
        # active configurations from being removed.
        decoy = mkdtemp()
        # the suite runs unprivileged, so the decoy mount needs sudo, and a
        # mode that still lets this test write the marker it checks below
        self.assertEqual(
            call(['sudo', 'mount', '-t', 'tmpfs', '-o', 'mode=1777', 'none', decoy]), 0
        )
        try:
            with open(f'{decoy}/marker', 'w') as f:
                f.write('untouched')
            os.symlink(decoy, planted_mnt)
            os.mkdir(planted_upper)

            a = self.sessions[0]
            for i in range(4):
                a.set(base_path + [f'{host_prefix}-0', 'inet'], f'10.91.3.{i + 1}')
                a.commit()

            self.assertEqual(mount_fstype(decoy), 'tmpfs', msg='a planted symlink was followed')
            with open(f'{decoy}/marker') as f:
                self.assertEqual(f.read(), 'untouched')
            # the idle sessions all still use the tree they started on; every
            # tree replaced after that is unused and gone
            self.assertEqual(len(old_active_trees()), 1, msg=old_active_trees())
            # and the tree they use is intact
            b = self.sessions[1]
            self.assertIn(f'{host_prefix}-0 ', b.show())
            self.assertIn('10.91.3.4', b.show())
        finally:
            remove_planted()
            call(['sudo', 'umount', decoy])
            os.rmdir(decoy)

    def test_helper_refuses_planted_upper(self):
        # The overlay writes into its upper layer with the privilege of
        # whoever mounted it, so an upper layer that is a symlink would land
        # those writes wherever it points. The kernel keeps the upper layer on
        # the work directory's filesystem, so the decoy lives in the
        # configuration root, as e.g. the active configuration does.
        decoy = mkdtemp(dir=config_dir)
        try:
            os.mkdir(planted_mnt)
            os.symlink(decoy, planted_upper)
            rc = call([OVL_HELPER, 'mount', bogus_sid], stdout=DEVNULL, stderr=DEVNULL)
            self.assertNotEqual(rc, 0)
            self.assertNotIn(planted_mnt, overlay_mounts())
            self.assertEqual(os.listdir(decoy), [])

            # the same session with a real upper layer mounts, so the refusal
            # above was the symlink and nothing else
            os.unlink(planted_upper)
            os.mkdir(planted_upper)
            rc = call([OVL_HELPER, 'mount', bogus_sid], stdout=DEVNULL, stderr=DEVNULL)
            self.assertEqual(rc, 0)
            self.assertIn(planted_mnt, overlay_mounts())
        finally:
            remove_planted()
            shutil.rmtree(decoy)

    def test_work_root_is_recreated_and_checked(self):
        # The configuration root is a fresh tmpfs on every boot, so the helper
        # creates the overlay work root itself. Anything it finds there that is
        # not its own directory must be refused, or the removals it does in
        # there could be aimed elsewhere.
        for session in self.sessions:
            session.teardown()
        self.sessions = []
        if os.path.isdir(ovl_work_dir) and os.listdir(ovl_work_dir):
            self.skipTest('other configuration sessions are open')

        decoy = mkdtemp()
        os.mkdir(f'{decoy}/{bogus_sid}')
        try:
            if os.path.isdir(ovl_work_dir):
                os.rmdir(ovl_work_dir)
            os.mkdir(planted_mnt)
            os.mkdir(planted_upper)

            os.symlink(decoy, ovl_work_dir)
            rc = call([OVL_HELPER, 'mount', bogus_sid], stdout=DEVNULL, stderr=DEVNULL)
            self.assertNotEqual(rc, 0)
            self.assertNotIn(planted_mnt, overlay_mounts())
            self.assertEqual(os.listdir(decoy), [bogus_sid])
            self.assertEqual(os.listdir(f'{decoy}/{bogus_sid}'), [])

            # as after a reboot: no work root at all
            os.unlink(ovl_work_dir)
            rc = call([OVL_HELPER, 'mount', bogus_sid], stdout=DEVNULL, stderr=DEVNULL)
            self.assertEqual(rc, 0)
            self.assertIn(planted_mnt, overlay_mounts())
            self.assertTrue(os.path.isdir(ovl_work_dir))
            self.assertFalse(os.path.islink(ovl_work_dir))
        finally:
            if os.path.islink(ovl_work_dir):
                os.unlink(ovl_work_dir)
            remove_planted()
            shutil.rmtree(decoy)

    def test_root_written_nodes_do_not_lose_session(self):
        # Op-mode scripts run via sudo and may write into the caller's session.
        # Nodes created that way are root-owned in the upper layer, and clearing
        # it as the session user after commit or discard used to fail and drop
        # the session.
        session = self.sessions[0]
        root_set = ['sudo', '--preserve-env', f'{SBIN}/my_set']

        session.run(root_set + base_path + [f'{host_prefix}-0', 'inet', '10.91.3.1'])
        session.commit()
        self.assertIn(f'{host_prefix}-0 ', session.show_active())

        session.run(root_set + base_path + [f'{host_prefix}-1', 'inet', '10.91.3.2'])
        session.discard()
        self.assertNotIn(f'{host_prefix}-1 ', session.show())

        # still a usable session
        session.set(base_path + [f'{host_prefix}-2', 'inet'], '10.91.3.3')
        session.commit()

    def test_work_root_is_private(self):
        # The helper removes things below the work root as root, so nobody
        # else may be able to place anything there; and the session
        # directories must not be renamable by other users.
        st = os.stat(ovl_work_dir)
        self.assertEqual(st.st_uid, 0)
        self.assertEqual(st.st_mode & 0o022, 0, msg=f'mode {oct(st.st_mode)}')
        self.assertTrue(os.stat(session_dir).st_mode & stat.S_ISVTX)

    def test_helper_ignores_hostile_caller_state(self):
        # The helper runs as root on behalf of the caller, who controls its
        # umask, limits and signals. None of that may change what it creates
        # or let it stop halfway.
        a = self.sessions[0]

        def hostile():
            os.umask(0o077)
            resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))

        for op in ('umount', 'mount'):
            rc = call([OVL_HELPER, op, a.sid], preexec_fn=hostile,
                      stdout=DEVNULL, stderr=DEVNULL)
            self.assertEqual(rc, 0, msg=op)
        self.assertIn(f'{session_dir}/new_config_{a.sid}', overlay_mounts())
        base = os.stat(f'{ovl_work_dir}/{a.sid}')
        self.assertEqual(base.st_mode & 0o777, 0o755)
        self.assertTrue(os.path.exists(f'{ovl_work_dir}/{a.sid}/lower'))
        a.set(base_path + [f'{host_prefix}-0', 'inet'], '10.91.6.1')
        a.commit()

    def test_commit_leaves_other_sessions_alone(self):
        # A commit never unmounts another session: doing so while that session
        # writes a change loses the change, although it was reported as made.
        a, b = self.sessions[0], self.sessions[1]
        b_mnt = f'{session_dir}/new_config_{b.sid}'
        before = mount_id(b_mnt)
        a.set(base_path + [f'{host_prefix}-0', 'inet'], '10.91.4.1')
        a.commit()
        self.assertEqual(mount_id(b_mnt), before)
        self.assertEqual(call([OVL_HELPER, 'restack', a.sid],
                              stdout=DEVNULL, stderr=DEVNULL), 2)
        self.assertEqual(mount_id(b_mnt), before)

        errors = []

        def committer():
            try:
                for i in range(10):
                    a.set(base_path + [f'{host_prefix}-0', 'inet'], f'10.91.5.{i + 1}')
                    a.commit()
            except Exception as e:  # noqa: BLE001 - reported below
                errors.append(str(e))

        t = Thread(target=committer)
        t.start()
        for i in range(40):
            b.set(base_path + [f'{host_prefix}-1-{i}', 'inet'], f'10.91.7.{i + 1}')
        t.join()
        self.assertEqual(errors, [])
        config = b.show()
        missing = [i for i in range(40) if f'{host_prefix}-1-{i} ' not in config]
        self.assertEqual(missing, [], msg='changes reported as made were lost')
        b.commit()
        active = a.show_active()
        self.assertIn('10.91.5.10', active)
        self.assertIn(f'{host_prefix}-1-39 ', active)

    def test_load_into_a_stale_session(self):
        # Loading compares the file with the active configuration and applies
        # the difference to the working one. Applied to a view of a superseded
        # active configuration, the result would differ from the file, so a
        # session that cannot be moved onto the current one must refuse.
        a, b, c = self.sessions[0], self.sessions[1], self.sessions[2]
        b_mnt = f'{session_dir}/new_config_{b.sid}'
        a.set(base_path + [f'{host_prefix}-0', 'inet'], '10.91.9.1')
        a.commit()
        b.show()  # b is now on the configuration that has the node

        saved = mkdtemp()
        busy = None
        try:
            config_file = f'{saved}/config.boot'
            with open(config_file, 'w') as f:
                f.write(c.show_active())

            busy = Popen(['sleep', '60'], cwd=b_mnt, stdout=DEVNULL, stderr=DEVNULL)
            a.delete(base_path + [f'{host_prefix}-0'])
            a.commit()
            with self.assertRaises(SessionError) as ctx:
                b.run([CLI_SHELL_API, 'loadFile', config_file])
            self.assertIn('Cannot load config', str(ctx.exception))
            busy.kill()
            busy.wait()
            busy = None

            b.run([CLI_SHELL_API, 'loadFile', config_file])
            b.commit()
            self.assertIn(f'{host_prefix}-0 ', a.show_active())
        finally:
            if busy:
                busy.kill()
                busy.wait()
            shutil.rmtree(saved)

    def test_commit_while_session_in_use(self):
        # Something else of the same session works on it while it commits.
        # The commit waits for it before remounting the session, and never
        # leaves what it committed in the session's upper layer, where it
        # would be applied again over later commits.
        a, b = self.sessions[0], self.sessions[1]
        lock = f'{session_dir}/tmp_{b.sid}/.session.lock'
        b.show()  # the session's first command creates its lock
        with Popen(['python3', '-c',
                    'import fcntl, sys, time\n'
                    'f = open(sys.argv[1])\n'
                    'fcntl.flock(f, fcntl.LOCK_SH)\n'
                    'print("held", flush=True)\n'
                    'time.sleep(4)\n', lock],
                   stdout=PIPE, stderr=DEVNULL) as holder:
            self.assertEqual(holder.stdout.readline().strip(), b'held')
            b.set(base_path + [f'{host_prefix}-1', 'inet'], '10.91.10.1')
            b.commit()

        # another session removes it again; b's next commit must not bring
        # it back
        a.delete(base_path + [f'{host_prefix}-1'])
        a.commit()
        b.set(base_path + [f'{host_prefix}-2', 'inet'], '10.91.10.3')
        b.commit()
        active = a.show_active()
        self.assertNotIn(f'{host_prefix}-1 ', active)
        self.assertIn(f'{host_prefix}-2 ', active)

    def test_unmounted_session_is_not_a_session(self):
        # Without its overlay a session directory reads as an empty
        # configuration, and committing from it deleted everything else.
        a, b = self.sessions[0], self.sessions[1]
        a.set(base_path + [f'{host_prefix}-0', 'inet'], '10.91.4.1')
        a.commit()
        before = b.show_active()

        self.assertEqual(call(['sudo', 'umount', f'{session_dir}/new_config_{a.sid}']), 0)
        with self.assertRaises(SessionError):
            a.set(base_path + [f'{host_prefix}-1', 'inet'], '10.91.4.2')
        with self.assertRaises(SessionError):
            a.commit()
        self.assertEqual(b.show_active(), before)

        # entering configuration mode again brings the session back
        a.run([CLI_SHELL_API, 'setupSession'])
        self.assertIn(f'{session_dir}/new_config_{a.sid}', overlay_mounts())
        a.set(base_path + [f'{host_prefix}-1', 'inet'], '10.91.4.2')
        a.commit()
        self.assertIn(f'{host_prefix}-0 ', b.show_active())

    def test_busy_stale_session_cannot_commit(self):
        # A session that was in use when somebody else committed cannot be
        # moved onto the new configuration until it is no longer in use. Its
        # commit must refuse until then rather than revert the other commit.
        a, b = self.sessions[0], self.sessions[1]
        b_mnt = f'{session_dir}/new_config_{b.sid}'
        b.set(base_path + [f'{host_prefix}-1', 'inet'], '10.91.8.2')

        busy = Popen(['sleep', '60'], cwd=b_mnt, stdout=DEVNULL, stderr=DEVNULL)
        try:
            a.set(base_path + [f'{host_prefix}-0', 'inet'], '10.91.8.1')
            a.commit()
            with self.assertRaises(SessionError) as ctx:
                b.commit()
            self.assertIn('in use', str(ctx.exception))
            self.assertIn(f'{host_prefix}-0 ', b.show_active())
        finally:
            busy.kill()
            busy.wait()

        b.commit()
        active = a.show_active()
        self.assertIn(f'{host_prefix}-0 ', active)
        self.assertIn(f'{host_prefix}-1 ', active)

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

    def test_helper_output_never_holds_a_lock(self):
        # The helper writes to whatever its caller made stdout and stderr,
        # pipes nobody reads included. Blocked on that, it must hold neither
        # the session's lock nor the one commits take to replace the active
        # configuration.
        a, b = self.sessions[0], self.sessions[1]
        host = base_path + [f'{host_prefix}-0']
        a.set(host + ['inet'], '10.91.15.1')
        a.set(host + ['alias'], 'al-1')
        a.commit()
        b.show()  # b moves onto that commit
        b.set(host + ['alias'], 'al-b')
        a.set(host + ['alias'], 'al-a')
        a.commit()  # moving b now drops its edit and lists it on stderr

        r, w = os.pipe()
        os.set_blocking(w, False)
        try:
            while True:
                os.write(w, b'x' * 65536)
        except BlockingIOError:
            pass
        os.set_blocking(w, True)
        helper = Popen([OVL_HELPER, 'refresh', b.sid], stdout=w, stderr=w)
        try:
            sleep(1)
            self.assertIsNone(helper.poll(), msg='the helper did not block on its output')
            self.assertEqual(
                call(['flock', '-n', '-x', f'{config_dir}/.tree.lock', 'true']), 0,
                msg='a commit would wait for the blocked helper',
            )
            self.assertEqual(
                call([OVL_HELPER, 'refresh', b.sid], stdout=DEVNULL, stderr=DEVNULL,
                     timeout=10), 0,
                msg='the session waits for the blocked helper',
            )
        finally:
            # running as root it cannot be signalled; reading lets it finish
            os.close(w)
            with os.fdopen(r, 'rb') as f:
                f.read()
            helper.wait(timeout=10)


if __name__ == '__main__':
    unittest.main(verbosity=2)
