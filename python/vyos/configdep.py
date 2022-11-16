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
from inspect import stack

from vyos.util import load_as_module

dependents = {}

def canon_name(name: str) -> str:
    return os.path.splitext(name)[0].replace('-', '_')

def canon_name_of_path(path: str) -> str:
    script = os.path.basename(path)
    return canon_name(script)

def caller_name() -> str:
    return stack()[-1].filename

def run_config_mode_script(script: str, config):
    from vyos.defaults import directories

    path = os.path.join(directories['conf_mode'], script)
    name = canon_name(script)
    mod = load_as_module(name, path)

    config.set_level([])
    try:
        c = mod.get_config(config)
        mod.verify(c)
        mod.generate(c)
        mod.apply(c)
    except (VyOSError, ConfigError) as e:
        raise ConfigError(repr(e))

def def_closure(script: str, config):
    def func_impl():
        run_config_mode_script(script, config)
    return func_impl

def set_dependent(target: str, config):
    k = canon_name_of_path(caller_name())
    l = dependents.setdefault(k, [])
    func = def_closure(target, config)
    l.append(func)

def call_dependents():
    k = canon_name_of_path(caller_name())
    l = dependents.get(k, [])
    while l:
        f = l.pop(0)
        f()
