#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

import os
import re
import json
import unittest
import warnings
import importlib.util
from inspect import signature, getsource
from functools import wraps

from vyos.defaults import directories

INC_FILE = '/usr/share/vyos/configd-include.json'
CONF_DIR = directories['conf_mode']

f_list = ['get_config', 'verify', 'generate', 'apply']

def import_script(s):
    path = os.path.join(CONF_DIR, s)
    name = os.path.splitext(s)[0].replace('-', '_')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# importing conf_mode scripts imports jinja2 with deprecation warning
def ignore_deprecation_warning(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            f(*args, **kwargs)
    return decorated_function

class TestConfigdInclude(unittest.TestCase):
    def setUp(self):
        with open(INC_FILE) as f:
            self.inc_list = json.load(f)

    @ignore_deprecation_warning
    def test_signatures(self):
        for s in self.inc_list:
            m = import_script(s)
            for i in f_list:
                f = getattr(m, i, None)
                if not f:
                    continue
                sig = signature(f)
                par = sig.parameters
                l = len(par)
                self.assertEqual(l, 1,
                        f"'{s}': '{i}' incorrect signature")
                if i == 'get_config':
                    for p in par.values():
                        self.assertTrue(p.default is None,
                                f"'{s}': '{i}' incorrect signature")

    @ignore_deprecation_warning
    def test_function_instance(self):
        for s in self.inc_list:
            m = import_script(s)
            for i in f_list:
                f = getattr(m, i, None)
                if not f:
                    continue
                str_f = getsource(f)
                # Regex not XXXConfig() T3108
                n = len(re.findall(r'[^a-zA-Z]Config\(\)', str_f))
                if i == 'get_config':
                    self.assertEqual(n, 1,
                            f"'{s}': '{i}' no instance of Config")
                if i != 'get_config':
                    self.assertEqual(n, 0,
                            f"'{s}': '{i}' instance of Config")

    @ignore_deprecation_warning
    def test_file_instance(self):
        for s in self.inc_list:
            m = import_script(s)
            str_m = getsource(m)
            # Regex not XXXConfig T3108
            n = len(re.findall(r'[^a-zA-Z]Config\(\)', str_m))
            self.assertEqual(n, 1,
                    f"'{s}' more than one instance of Config")

    @ignore_deprecation_warning
    def test_config_modification(self):
        for s in self.inc_list:
            m = import_script(s)
            str_m = getsource(m)
            n = str_m.count('my_set')
            self.assertEqual(n, 0, f"'{s}' modifies config")

if __name__ == '__main__':
    unittest.main(verbosity=2)
