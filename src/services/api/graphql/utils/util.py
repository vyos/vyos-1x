# Copyright 2022 VyOS maintainers and contributors <maintainers@vyos.io>
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

import os
import re
import importlib.util

from vyos.defaults import directories

def load_as_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def load_op_mode_as_module(name: str):
    path = os.path.join(directories['op_mode'], name)
    name = os.path.splitext(name)[0]
    return load_as_module(name, path)

def is_op_mode_function_name(name):
    if re.match(r"^(show|clear|reset|restart)", name):
        return True
    return False

def is_show_function_name(name):
    if re.match(r"^show", name):
        return True
    return False
