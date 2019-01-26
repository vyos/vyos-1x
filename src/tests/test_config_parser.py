#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
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
#

import os
import tempfile
import unittest
from unittest import TestCase, mock

import vyos.configtree


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
        # No sorting is intentional, child order must be preserved
        self.assertEqual(self.config.list_nodes(["top-level-tag-node"]), ["foo", "bar"])
