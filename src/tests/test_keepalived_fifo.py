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
# Regression coverage for T9256 defect 1: the notify-line regex used to
# reject any VRRP group/sync-group name containing a character outside
# [\w-] (colons, dots, spaces, slashes - anything the CLI's tag-node
# tokenizer actually accepts), so transition-script never even matched.
#
# Widening the regex (#5468) is only half of the fix. The two lookups
# that turn a matched name into a transition-script command used to build
# an f-string path and hand it to dict_search(), which splits on '.' - so
# a name containing a literal dot broke the lookup again, one call deeper
# than the regex, with the exact same silent-no-op symptom. This is what
# a maintainer review on #5468 caught after the regex fix alone shipped.
#
# These tests exercise the regex and the lookup together, for every
# character class the underlying bug report (T9256) showed the CLI
# actually accepts, so a name reaching its transition-script command is
# proven end to end and not just "the regex matched it".

import os
import re
import unittest

from helper import prepare_module

_here = os.path.dirname(__file__)

fifo_module = prepare_module(
    os.path.join(_here, '../system/keepalived-fifo.py'), 'keepalived_fifo'
)

# same pattern as regex_notify in KeepalivedFifo.pipe_process() - kept
# separate here since it is a local variable there, not importable
NOTIFY_RE = re.compile(
    r'^(?P<type>\w+) "(?P<name>[^"]+)" (?P<state>\w+) (?P<priority>\d+)$', re.MULTILINE
)


class TestNotifyRegex(unittest.TestCase):
    """Names containing characters outside [\\w-] must still be captured
    whole out of the keepalived notify line - this is the literal T9256
    defect 1 symptom (INSTANCE "cluster:999v6" MASTER 100 never matched).
    """

    def test_colon_in_name(self):
        m = NOTIFY_RE.search('INSTANCE "cluster:999v6" MASTER 100')
        self.assertEqual(m.group('name'), 'cluster:999v6')

    def test_dot_in_name(self):
        m = NOTIFY_RE.search('INSTANCE "cluster.1" BACKUP 200')
        self.assertEqual(m.group('name'), 'cluster.1')

    def test_space_in_name(self):
        m = NOTIFY_RE.search('INSTANCE "with space" MASTER 100')
        self.assertEqual(m.group('name'), 'with space')

    def test_slash_in_name(self):
        m = NOTIFY_RE.search('GROUP "with/slash" FAULT 0')
        self.assertEqual(m.group('name'), 'with/slash')

    def test_unquoted_message_not_matched(self):
        # a message with no quoted name at all (e.g. a line that isn't a
        # notify line in this format) must not match
        self.assertIsNone(NOTIFY_RE.search('some unrelated log line'))


class TestTransitionScriptLookup(unittest.TestCase):
    """The regex match is only half of it: the fix in #5468 widened what
    pipe_process() *matches*, but the two lookups that turn a matched name
    into a command used to build a dot-delimited f-string path and hand it
    to dict_search() - reproducing the same silent no-op for any name
    containing a literal '.'. lookup_transition_script() replaces both
    call sites with dict_search_args(), which indexes by exact key and
    never parses the name at all. These tests call it against a dict
    shaped like ConfigTreeQuery().get_config_dict() actually returns it
    (no_tag_node_value_mangle=True keeps the name key exactly as the CLI
    accepted it).
    """

    def _config_with(self, kind, name, state, command):
        return {kind: {name: {'transition_script': {state: command}}}}

    def test_instance_name_with_dot_found(self):
        cfg = self._config_with(
            'group', 'cluster.1', 'master', '/config/scripts/on-master.sh'
        )
        cmd = fifo_module.lookup_transition_script(cfg, 'group', 'cluster.1', 'MASTER')
        self.assertEqual(cmd, '/config/scripts/on-master.sh')

    def test_sync_group_name_with_dot_found(self):
        cfg = self._config_with(
            'sync_group', 'cluster.HA', 'fault', '/config/scripts/on-fault.sh'
        )
        cmd = fifo_module.lookup_transition_script(
            cfg, 'sync_group', 'cluster.HA', 'FAULT'
        )
        self.assertEqual(cmd, '/config/scripts/on-fault.sh')

    def test_name_with_colon_found(self):
        cfg = self._config_with(
            'group', 'cluster:11', 'backup', '/config/scripts/on-backup.sh'
        )
        cmd = fifo_module.lookup_transition_script(cfg, 'group', 'cluster:11', 'BACKUP')
        self.assertEqual(cmd, '/config/scripts/on-backup.sh')

    def test_name_with_space_and_slash_found(self):
        cfg = self._config_with('group', 'a b/c', 'master', '/config/scripts/x.sh')
        cmd = fifo_module.lookup_transition_script(cfg, 'group', 'a b/c', 'MASTER')
        self.assertEqual(cmd, '/config/scripts/x.sh')

    def test_name_with_multiple_dots_found(self):
        # the case that would silently break worst under the old
        # f'group.{name}...' + dict_search() path: every dot in the name
        # adds a spurious path component
        cfg = self._config_with('group', 'a.b.c', 'master', '/config/scripts/y.sh')
        cmd = fifo_module.lookup_transition_script(cfg, 'group', 'a.b.c', 'MASTER')
        self.assertEqual(cmd, '/config/scripts/y.sh')

    def test_no_transition_script_configured_returns_none(self):
        cfg = {'group': {'cluster.1': {}}}
        cmd = fifo_module.lookup_transition_script(cfg, 'group', 'cluster.1', 'MASTER')
        self.assertIsNone(cmd)

    def test_script_configured_for_other_state_returns_none(self):
        # only 'master' has a script - a 'backup' notification for the
        # same name must not fall back to it
        cfg = self._config_with(
            'group', 'cluster.1', 'master', '/config/scripts/on-master.sh'
        )
        cmd = fifo_module.lookup_transition_script(cfg, 'group', 'cluster.1', 'BACKUP')
        self.assertIsNone(cmd)

    def test_group_key_entirely_absent(self):
        # a config with only sync-groups (no VRRP instances at all) - the
        # top-level 'group' key itself is missing, not just empty
        cfg = {'sync_group': {'cluster': {}}}
        cmd = fifo_module.lookup_transition_script(cfg, 'group', 'cluster.1', 'MASTER')
        self.assertIsNone(cmd)

    def test_empty_config_dict_returns_none(self):
        # defensive: must not raise even if vrrp_config_dict is empty
        cmd = fifo_module.lookup_transition_script({}, 'group', 'cluster.1', 'MASTER')
        self.assertIsNone(cmd)

    def test_unrelated_name_not_matched(self):
        # regression guard for the false-positive direction: a dotted
        # name must not accidentally resolve to a DIFFERENT instance's
        # script just because dict_search() would have walked into it
        cfg = self._config_with('group', 'cluster.1', 'master', '/config/scripts/x.sh')
        cmd = fifo_module.lookup_transition_script(cfg, 'group', 'cluster.2', 'MASTER')
        self.assertIsNone(cmd)

    def test_group_and_sync_group_kept_separate(self):
        cfg = {
            'group': self._config_with(
                'group', 'cluster.1', 'master', '/config/scripts/instance.sh'
            )['group'],
            'sync_group': self._config_with(
                'sync_group', 'cluster.1', 'master', '/config/scripts/sync.sh'
            )['sync_group'],
        }
        self.assertEqual(
            fifo_module.lookup_transition_script(cfg, 'group', 'cluster.1', 'MASTER'),
            '/config/scripts/instance.sh',
        )
        self.assertEqual(
            fifo_module.lookup_transition_script(
                cfg, 'sync_group', 'cluster.1', 'MASTER'
            ),
            '/config/scripts/sync.sh',
        )


if __name__ == '__main__':
    unittest.main()
