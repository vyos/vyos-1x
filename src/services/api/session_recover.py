# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

"""HTTP API recovery when the long-lived ConfigSession backend is gone.

ConfigSession stays a thin wrapper of the config backend. Recreating
ConfigSession(pid) is the same initialization the API process does at
start — not ConfigSession self-repair (T9130 / jestabro).
"""

import logging
import os

LOG = logging.getLogger('http_api.session')

# Substring from cli-shell-api / my_* when the config session is gone.
SESSION_LOST_MARKER = 'without config session'
SESSION_UNAVAILABLE = 'config session unavailable; retry'


def is_session_lost(err: BaseException) -> bool:
    return SESSION_LOST_MARKER in str(err)


def abandon_session(session) -> None:
    """Stop GC teardown of the dead object so it cannot race the replacement.

    Old and new ConfigSession share the process PID as session id; the
    leftover weakref finalizer would teardownSession the new one.
    """
    if session is None:
        return
    session.shared = True
    finalizer = getattr(session, '_finalizer', None)
    if finalizer is not None:
        finalizer.detach()
        session._finalizer = None


def recreate_config_session(state, config_session_cls=None) -> bool:
    """Replace state.session with a newly constructed ConfigSession.

    Caller must hold the configure lock. Returns True if state.session
    is set afterward.
    """
    if config_session_cls is None:
        from vyos.configsession import ConfigSession as config_session_cls

    abandon_session(getattr(state, 'session', None))
    try:
        state.session = config_session_cls(os.getpid())
        LOG.warning('HTTP API config session recreated')
        return True
    except Exception as e:
        LOG.error('failed to recreate HTTP API config session: %s', e)
        state.session = None
        return False


def safe_discard(session) -> None:
    """discard() without turning a dead session into a second exception."""
    if session is None:
        return
    try:
        session.discard()
    except Exception as err:
        if not is_session_lost(err):
            raise
