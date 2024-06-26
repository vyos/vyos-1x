# Copyright (C) 2018-2024 VyOS maintainers and contributors
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

class TestConfigParser(TestCase):
    def setUp(self):
        with open('tests/data/config.valid', 'r') as f:
            config_string = f.read()
            self.config = vyos.configtree.ConfigTree(config_string)

    def test_top_level_valueless(self):
        self.assertTrue(self.config.exists(["top-level-valueless-node"]))

    def test_top_level_leaf(self):
        self.assertTrue(self.config.exists(["top-level-leaf-node"]))
        self.assertEqual(self.config.return_value(["top-level-leaf-node"]), "foo")

    def test_top_level_tag(self):
        self.assertTrue(self.config.exists(["top-level-tag-node"]))
        # Sorting is now intentional, during parsing of config
        self.assertEqual(self.config.list_nodes(["top-level-tag-node"]), ["bar", "foo"])

    def test_copy(self):
        self.config.copy(["top-level-tag-node", "bar"], ["top-level-tag-node", "baz"])
        print(self.config.to_string())
        self.assertTrue(self.config.exists(["top-level-tag-node", "baz"]))

    def test_copy_duplicate(self):
        with self.assertRaises(vyos.configtree.ConfigTreeError):
            self.config.copy(["top-level-tag-node", "foo"], ["top-level-tag-node", "bar"])

    def test_rename(self):
        self.config.rename(["top-level-tag-node", "bar"], "quux")
        print(self.config.to_string())
        self.assertTrue(self.config.exists(["top-level-tag-node", "quux"]))

    def test_rename_duplicate(self):
        with self.assertRaises(vyos.configtree.ConfigTreeError):
            self.config.rename(["top-level-tag-node", "foo"], "bar")
