# Copyright (C) 2020-2025 VyOS maintainers and contributors
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

import ast
import json

from unittest import TestCase

INC_FILE = 'data/configd-include.json'
CONF_DIR = 'src/conf_mode'

funcs = ['get_config', 'verify', 'generate', 'apply']


class FunctionSig(ast.NodeVisitor):
    def __init__(self):
        self.func_sig_len = dict.fromkeys(funcs, None)
        self.get_config_default_values = []

    def visit_FunctionDef(self, node):
        func_name = node.name
        if func_name in funcs:
            self.func_sig_len[func_name] = len(node.args.args)

        if func_name == 'get_config':
            for default in node.args.defaults:
                if isinstance(default, ast.Constant):
                    self.get_config_default_values.append(default.value)

        self.generic_visit(node)

    def get_sig_lengths(self):
        return self.func_sig_len

    def get_config_default(self):
        return self.get_config_default_values[0]


class LegacyCall(ast.NodeVisitor):
    def __init__(self):
        self.legacy_func_count = 0

    def visit_Constant(self, node):
        value = node.value
        if isinstance(value, str):
            if 'my_set' in value or 'my_delete' in value:
                self.legacy_func_count += 1

        self.generic_visit(node)

    def get_legacy_func_count(self):
        return self.legacy_func_count


class ConfigInstance(ast.NodeVisitor):
    def __init__(self):
        self.count = 0

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name == 'Config':
                self.count += 1
        self.generic_visit(node)

    def get_count(self):
        return self.count


class FunctionConfigInstance(ast.NodeVisitor):
    def __init__(self):
        self.func_config_instance = dict.fromkeys(funcs, 0)

    def visit_FunctionDef(self, node):
        func_name = node.name
        if func_name in funcs:
            config_instance = ConfigInstance()
            config_instance.visit(node)
            self.func_config_instance[func_name] = config_instance.get_count()
        self.generic_visit(node)

    def get_func_config_instance(self):
        return self.func_config_instance


class TestConfigdInspect(TestCase):
    def setUp(self):
        self.ast_list = []

        with open(INC_FILE) as f:
            self.inc_list = json.load(f)

        for s in self.inc_list:
            s_path = f'{CONF_DIR}/{s}'
            with open(s_path) as f:
                s_str = f.read()
            s_tree = ast.parse(s_str)
            self.ast_list.append((s, s_tree))

    def test_signatures(self):
        for s, t in self.ast_list:
            visitor = FunctionSig()
            visitor.visit(t)
            sig_lens = visitor.get_sig_lengths()

            for f in funcs:
                self.assertIsNotNone(sig_lens[f], f"'{s}': '{f}' missing")
                self.assertEqual(sig_lens[f], 1, f"'{s}': '{f}' incorrect signature")

            self.assertEqual(
                visitor.get_config_default(),
                None,
                f"'{s}': 'get_config' incorrect signature",
            )

    def test_file_config_instance(self):
        for s, t in self.ast_list:
            visitor = ConfigInstance()
            visitor.visit(t)
            count = visitor.get_count()

            self.assertEqual(count, 1, f"'{s}' more than one instance of Config")

    def test_function_config_instance(self):
        for s, t in self.ast_list:
            visitor = FunctionConfigInstance()
            visitor.visit(t)
            func_config_instance = visitor.get_func_config_instance()

            for f in funcs:
                if f == 'get_config':
                    self.assertTrue(
                        func_config_instance[f] > 0,
                        f"'{s}': '{f}' no instance of Config",
                    )
                    self.assertTrue(
                        func_config_instance[f] < 2,
                        f"'{s}': '{f}' more than one instance of Config",
                    )
                else:
                    self.assertEqual(
                        func_config_instance[f], 0, f"'{s}': '{f}' instance of Config"
                    )

    def test_config_modification(self):
        for s, t in self.ast_list:
            visitor = LegacyCall()
            visitor.visit(t)
            legacy_func_count = visitor.get_legacy_func_count()

            self.assertEqual(legacy_func_count, 0, f"'{s}' modifies config")
