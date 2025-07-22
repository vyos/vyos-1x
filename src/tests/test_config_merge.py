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

import vyos.configtree

from unittest import TestCase

class TestConfigDiff(TestCase):
    def setUp(self):
        with open('tests/data/config.left', 'r') as f:
            config_string = f.read()
            self.config_left = vyos.configtree.ConfigTree(config_string)

        with open('tests/data/config.right', 'r') as f:
            config_string = f.read()
            self.config_right = vyos.configtree.ConfigTree(config_string)

    def test_merge_destructive(self):
        res = vyos.configtree.merge(self.config_left, self.config_right,
                                    destructive=True)
        right_value = self.config_right.return_value(['node1', 'tag_node', 'foo', 'single'])
        merge_value = res.return_value(['node1', 'tag_node', 'foo', 'single'])

        # Check includes new value
        self.assertEqual(right_value, merge_value)

        # Check preserves non-confliciting paths
        self.assertTrue(res.exists(['node3']))

    def test_merge_non_destructive(self):
        res = vyos.configtree.merge(self.config_left, self.config_right)
        left_value = self.config_left.return_value(['node1', 'tag_node', 'foo', 'single'])
        merge_value = res.return_value(['node1', 'tag_node', 'foo', 'single'])

        # Check includes original value
        self.assertEqual(left_value, merge_value)

        # Check preserves non-confliciting paths
        self.assertTrue(res.exists(['node3']))
