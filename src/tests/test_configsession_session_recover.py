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

"""Unit tests for ConfigSession mid-life session recovery helpers.

These do not require a live cli-shell-api; they mock the low-level command path.
"""

import sys
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import patch

# Host checkouts (macOS/dev) may lack VyOS packaging deps; stub before import.
for _mod in (
    'cracklib',
    'requests',
    'psutil',
    'hurry',
    'hurry.filesize',
    'google',
    'google.protobuf',
    'vyos.vyconf_session',
    'vyos.proto',
    'vyos.proto.vyconf_pb2',
    'vyos.proto.vyconf_client',
):
    sys.modules.setdefault(_mod, MagicMock())

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError


def _make_session_stub() -> ConfigSession:
    """Build a ConfigSession-like object without calling real setupSession."""
    obj = ConfigSession.__new__(ConfigSession)
    obj._ConfigSession__session_id = 12345
    obj._ConfigSession__session_env = {'SESSION_PID': '12345'}
    obj._vyconf_session = None
    obj._finalizer = None
    # Avoid __del__ teardown against a missing cli-shell-api on host checkouts.
    obj.shared = True
    return obj


class TestConfigSessionRecover(TestCase):
    def test_session_exists_true(self):
        s = _make_session_stub()
        with patch.object(s, '_ConfigSession__run_command', return_value='') as run:
            self.assertTrue(s.session_exists())
            run.assert_called_once()
            args = run.call_args[0][0]
            self.assertEqual(args[-1], 'inSession')

    def test_session_exists_false_on_error(self):
        s = _make_session_stub()
        with patch.object(
            s,
            '_ConfigSession__run_command',
            side_effect=ConfigSessionError(
                'calling validateSetPath() without config session'
            ),
        ):
            self.assertFalse(s.session_exists())

    def test_ensure_session_noop_when_alive(self):
        s = _make_session_stub()
        with patch.object(s, 'session_exists', return_value=True):
            with patch.object(s, '_ConfigSession__run_command') as run:
                self.assertTrue(s.ensure_session())
                run.assert_not_called()

    def test_ensure_session_re_setup_when_dead(self):
        s = _make_session_stub()
        # session_exists: False then True after setup
        exists = MagicMock(side_effect=[False, True])
        with patch.object(s, 'session_exists', exists):
            with patch('vyos.configsession.subprocess.check_output', return_value=b''):
                with patch.object(s, '_ConfigSession__run_command', return_value='') as run:
                    with patch('vyos.configsession.vyconf_backend', return_value=False):
                        with patch(
                            'vyos.configsession.boot_configuration_complete',
                            return_value=False,
                        ):
                            self.assertTrue(s.ensure_session())
                # setupSession invoked once
                self.assertEqual(run.call_count, 1)
                self.assertEqual(run.call_args[0][0][-1], 'setupSession')

    def test_ensure_session_rebinds_vyconf_finalizer(self):
        """Replacement VyconfSession must own the finalizer, not the stale one."""
        s = _make_session_stub()
        s.shared = False
        old_vyconf = MagicMock(name='old_vyconf')
        new_vyconf = MagicMock(name='new_vyconf')
        s._vyconf_session = old_vyconf
        old_finalizer = MagicMock(name='old_finalizer')
        s._finalizer = old_finalizer
        new_finalizer = MagicMock(name='new_finalizer')

        exists = MagicMock(side_effect=[False, True])
        with patch.object(s, 'session_exists', exists):
            with patch('vyos.configsession.subprocess.check_output', return_value=b''):
                with patch.object(s, '_ConfigSession__run_command', return_value=''):
                    with patch('vyos.configsession.vyconf_backend', return_value=True):
                        with patch(
                            'vyos.configsession.boot_configuration_complete',
                            return_value=True,
                        ):
                            with patch(
                                'vyos.configsession.VyconfSession',
                                return_value=new_vyconf,
                            ):
                                with patch(
                                    'vyos.configsession.weakref.finalize',
                                    return_value=new_finalizer,
                                ) as fin:
                                    self.assertTrue(s.ensure_session())

        old_finalizer.detach.assert_called_once()
        fin.assert_called_once()
        args = fin.call_args[0]
        self.assertIs(args[0], s)
        # classmethod bound to ConfigSession (same as __init__ path)
        self.assertEqual(args[1].__func__, ConfigSession.finalize_vyconf.__func__)
        self.assertIs(args[2], new_vyconf)
        self.assertIs(s._vyconf_session, new_vyconf)
        self.assertIs(s._finalizer, new_finalizer)

    def test_ensure_session_false_when_setup_fails(self):
        s = _make_session_stub()
        with patch.object(s, 'session_exists', return_value=False):
            with patch('vyos.configsession.subprocess.check_output', return_value=b''):
                with patch.object(
                    s,
                    '_ConfigSession__run_command',
                    side_effect=ConfigSessionError('setup failed'),
                ):
                    self.assertFalse(s.ensure_session())

    def test_ensure_session_clears_stale_vyconf_on_construct_fail(self):
        """VyconfSession() failure must not leave the old backend attached."""
        s = _make_session_stub()
        s.shared = False
        old_vyconf = MagicMock(name='old_vyconf')
        s._vyconf_session = old_vyconf
        old_finalizer = MagicMock(name='old_finalizer')
        s._finalizer = old_finalizer

        with patch.object(s, 'session_exists', return_value=False):
            with patch('vyos.configsession.subprocess.check_output', return_value=b''):
                with patch.object(s, '_ConfigSession__run_command', return_value=''):
                    with patch('vyos.configsession.vyconf_backend', return_value=True):
                        with patch(
                            'vyos.configsession.boot_configuration_complete',
                            return_value=True,
                        ):
                            with patch(
                                'vyos.configsession.VyconfSession',
                                side_effect=ConfigSessionError(
                                    'vyconf construct failed'
                                ),
                            ):
                                with patch(
                                    'vyos.configsession.weakref.finalize'
                                ) as fin:
                                    self.assertFalse(s.ensure_session())

        self.assertIsNone(s._vyconf_session)
        old_finalizer.detach.assert_called_once()
        # No new finalizer when backend is cleared
        fin.assert_not_called()
        self.assertIsNone(s._finalizer)

    def test_discard_noop_when_session_lost(self):
        s = _make_session_stub()
        with patch.object(
            s,
            '_ConfigSession__run_command',
            side_effect=ConfigSessionError(
                'calling discardChanges() without config session'
            ),
        ):
            # Must not raise
            s.discard()

    def test_discard_reraises_other_errors(self):
        s = _make_session_stub()
        with patch.object(
            s,
            '_ConfigSession__run_command',
            side_effect=ConfigSessionError('some other failure'),
        ):
            with self.assertRaises(ConfigSessionError):
                s.discard()
