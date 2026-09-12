#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.

"""HTTP API session re-init (T9130). ConfigSession is not self-repaired."""

import importlib
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

try:
    session_recover = importlib.import_module('src.services.api.session_recover')
except ModuleNotFoundError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
    session_recover = importlib.import_module('src.services.api.session_recover')

SESSION_UNAVAILABLE = session_recover.SESSION_UNAVAILABLE
abandon_session = session_recover.abandon_session
is_session_lost = session_recover.is_session_lost
recreate_config_session = session_recover.recreate_config_session
safe_discard = session_recover.safe_discard


class TestIsSessionLost(unittest.TestCase):
    def test_marker(self):
        self.assertTrue(
            is_session_lost(
                Exception('calling validateSetPath() without config session')
            )
        )
        self.assertFalse(is_session_lost(Exception('path is invalid')))


class TestAbandonSession(unittest.TestCase):
    def test_none(self):
        abandon_session(None)

    def test_detaches_finalizer(self):
        session = SimpleNamespace(shared=False)
        finalizer = MagicMock()
        session._finalizer = finalizer
        abandon_session(session)
        self.assertTrue(session.shared)
        finalizer.detach.assert_called_once()
        self.assertIsNone(session._finalizer)


class TestRecreateConfigSession(unittest.TestCase):
    def test_replaces_dead_session(self):
        old = SimpleNamespace(shared=False)
        finalizer = MagicMock()
        old._finalizer = finalizer
        state = SimpleNamespace(session=old)
        new = object()
        cls = MagicMock(return_value=new)
        with patch.object(os, 'getpid', return_value=12345):
            self.assertTrue(recreate_config_session(state, config_session_cls=cls))
        cls.assert_called_once_with(12345)
        self.assertIs(state.session, new)
        self.assertTrue(old.shared)
        finalizer.detach.assert_called_once()

    def test_construct_fail_clears_state(self):
        old = SimpleNamespace(shared=False, _finalizer=None)
        state = SimpleNamespace(session=old)
        cls = MagicMock(side_effect=RuntimeError('setupSession failed'))
        with patch.object(os, 'getpid', return_value=1):
            self.assertFalse(recreate_config_session(state, config_session_cls=cls))
        self.assertIsNone(state.session)


class TestSafeDiscard(unittest.TestCase):
    def test_none(self):
        safe_discard(None)

    def test_swallows_session_lost(self):
        session = MagicMock()
        session.discard.side_effect = Exception(
            'calling discardChanges() without config session'
        )
        safe_discard(session)

    def test_reraises_other_errors(self):
        session = MagicMock()
        session.discard.side_effect = Exception('uncommitted changes')
        with self.assertRaises(Exception):
            safe_discard(session)


class TestUnavailableMessage(unittest.TestCase):
    def test_message(self):
        self.assertIn('retry', SESSION_UNAVAILABLE)


if __name__ == '__main__':
    unittest.main()
