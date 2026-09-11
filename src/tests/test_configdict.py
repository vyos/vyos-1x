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

from unittest import TestCase
from unittest.mock import patch

from vyos.configdict import leaf_node_changed


class TestLeafNodeChanged(TestCase):
    """leaf_node_changed() reports the old value(s) of an altered leaf node.

    get_value_diff() reads the JSON rendering of the config tree, where a
    multi node holding a single value is a plain string and only becomes a
    list once it holds several values. A caller deleting whatever comes back
    must therefore never see a value that is still configured.
    """

    def _changed(self, new, old):
        # leaf_node_changed() imports get_config_diff() at call time
        with patch('vyos.configdiff.get_config_diff') as get_diff:
            get_diff.return_value.get_value_diff.return_value = (new, old)
            return leaf_node_changed(None, ['some', 'path'])

    def test_unchanged(self):
        self.assertIsNone(self._changed('eth1', 'eth1'))
        self.assertIsNone(self._changed(['eth1', 'eth2'], ['eth1', 'eth2']))

    def test_value_replaced(self):
        self.assertEqual(self._changed('eth2', 'eth1'), ['eth1'])

    def test_value_deleted(self):
        self.assertEqual(self._changed(None, 'eth1'), ['eth1'])
        self.assertEqual(self._changed(None, ['eth1', 'eth2']), ['eth1', 'eth2'])

    def test_value_added(self):
        self.assertEqual(self._changed('eth1', None), [])

    def test_valueless_node(self):
        self.assertTrue(self._changed(None, {}))
        self.assertTrue(self._changed({}, None))

    def test_appended_to_single_valued_multi_node(self):
        # T9269: the single configured value renders as a string while the two
        # configured values render as a list. Nothing was removed here - adding
        # a second bond member used to release the first one because this
        # returned ['eth1']
        self.assertEqual(self._changed(['eth1', 'eth2'], 'eth1'), [])

    def test_appended_to_multi_valued_multi_node(self):
        self.assertEqual(self._changed(['eth1', 'eth2', 'eth3'], ['eth1', 'eth2']), [])

    def test_replaced_in_multi_node(self):
        self.assertEqual(self._changed(['eth2', 'eth3'], 'eth1'), ['eth1'])
        self.assertEqual(self._changed(['eth1', 'eth3'], ['eth1', 'eth2']), ['eth2'])

    def test_shrunk_to_single_value(self):
        # and the reverse representation change: list back to plain string
        self.assertEqual(self._changed('eth1', ['eth1', 'eth2']), ['eth2'])
