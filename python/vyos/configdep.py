# Copyright 2023-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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
import json
import typing
from inspect import stack
from graphlib import TopologicalSorter, CycleError

from vyos.utils.system import load_as_module
from vyos.configdict import dict_merge
from vyos.defaults import directories
from vyos.configsource import VyOSError
from vyos import ConfigError

# https://peps.python.org/pep-0484/#forward-references
# for type 'Config'
if typing.TYPE_CHECKING:
    from vyos.config import Config

dependency_dir = os.path.join(directories['data'],
                              'config-mode-dependencies')

local_dependent_func: dict[str, list[typing.Callable]] = {}

DEBUG = False
FORCE_LOCAL = False

def debug_print(s: str):
    if DEBUG:
        print(s)

def canon_name(name: str) -> str:
    return os.path.splitext(name)[0].replace('-', '_')

def canon_name_of_path(path: str) -> str:
    script = os.path.basename(path)
    return canon_name(script)

def caller_name() -> str:
    return stack()[2].filename

def name_of(f: typing.Callable) -> str:
    return f.__name__

def names_of(l: list[typing.Callable]) -> list[str]:
    return [name_of(f) for f in l]

def remove_redundant(l: list[typing.Callable]) -> list[typing.Callable]:
    names = set()
    for e in reversed(l):
        _ = l.remove(e) if name_of(e) in names else names.add(name_of(e))

def append_uniq(l: list[typing.Callable], e: typing.Callable):
    """Append an element, removing earlier occurrences

    The list of dependencies is generally short and traversing the list on
    each append is preferable to the cost of redundant script invocation.
    """
    l.append(e)
    remove_redundant(l)

def read_dependency_dict(dependency_dir: str = dependency_dir) -> dict:
    res = {}
    for dep_file in os.listdir(dependency_dir):
        if not dep_file.endswith('.json'):
            continue
        path = os.path.join(dependency_dir, dep_file)
        with open(path) as f:
            d = json.load(f)
        if dep_file == 'vyos-1x.json':
            res = dict_merge(res, d)
        else:
            res = dict_merge(d, res)

    return res

def get_dependency_dict(config: 'Config') -> dict:
    if hasattr(config, 'cached_dependency_dict'):
        d = getattr(config, 'cached_dependency_dict')
    else:
        d = read_dependency_dict()
        setattr(config, 'cached_dependency_dict', d)
    return d

def run_config_mode_script(script: str, config: 'Config'):
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

def def_closure(target: str, config: 'Config',
                tagnode: typing.Optional[str] = None) -> typing.Callable:
    script = target + '.py'
    def func_impl():
        if tagnode:
            os.environ['VYOS_TAGNODE_VALUE'] = tagnode
        run_config_mode_script(script, config)
    return func_impl

def set_dependents(case: str, config: 'Config',
                   tagnode: typing.Optional[str] = None):
    d = get_dependency_dict(config)
    k = canon_name_of_path(caller_name())
    tag_ext = f'_{tagnode}' if tagnode is not None else ''
    if hasattr(config, 'dependent_func') and not FORCE_LOCAL:
        dependent_func = getattr(config, 'dependent_func')
        l = dependent_func.setdefault('vyos_configd', [])
    else:
        dependent_func = local_dependent_func
        l = dependent_func.setdefault(k, [])
    for target in d[k][case]:
        func = def_closure(target, config, tagnode)
        func.__name__ = f'{target}{tag_ext}'
        append_uniq(l, func)
    debug_print(f'set_dependents: caller {k}, dependents {names_of(l)}')

def call_dependents(dependent_func: dict = None):
    k = canon_name_of_path(caller_name())
    if dependent_func is None or FORCE_LOCAL:
        dependent_func = local_dependent_func
        l = dependent_func.get(k, [])
    else:
        l = dependent_func.get('vyos_configd', [])
    debug_print(f'call_dependents: caller {k}, dependents {names_of(l)}')
    while l:
        f = l.pop(0)
        debug_print(f'calling: {f.__name__}')
        f()

def called_as_dependent() -> bool:
    st = stack()[1:]
    for f in st:
        if f.filename == __file__:
            return True
    return False

def graph_from_dependency_dict(d: dict) -> dict:
    g = {}
    for k in list(d):
        g[k] = set()
        # add the dependencies for every sub-case; should there be cases
        # that are mutally exclusive in the future, the graphs will be
        # distinguished
        for el in list(d[k]):
            g[k] |= set(d[k][el])

    return g

def is_acyclic(d: dict) -> bool:
    g = graph_from_dependency_dict(d)
    ts = TopologicalSorter(g)
    try:
        # get node iterator
        order = ts.static_order()
        # try iteration
        _ = [*order]
    except CycleError:
        return False

    return True

def check_dependency_graph(dependency_dir: str = dependency_dir,
                           supplement: str = None) -> bool:
    d = read_dependency_dict(dependency_dir=dependency_dir)
    if supplement is not None:
        with open(supplement) as f:
            d = dict_merge(json.load(f), d)

    return is_acyclic(d)
