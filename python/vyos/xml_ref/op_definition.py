# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

from typing import TypeAlias
from typing import Union
from typing import Optional
from typing import Iterator
from dataclasses import dataclass
from dataclasses import field
from dataclasses import fields
from dataclasses import asdict
from itertools import filterfalse


@dataclass
class NodeData:
    # pylint: disable=too-many-instance-attributes
    name: str = ''
    node_type: str = 'node'
    help_text: str = ''
    comp_help: dict[str, list] = field(default_factory=dict)
    command: str = ''
    standalone_help_text: Optional[str] = None
    standalone_command: Optional[str] = None
    constraints: Optional[dict] = None
    constraint_error_message: Optional[str] = None
    path: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    children: list[tuple] = field(default_factory=list)


OpKey: TypeAlias = tuple[str, str]
OpData: TypeAlias = dict[OpKey, Union[NodeData, 'OpData']]


def key_name(k: OpKey):
    return k[0]


def key_type(k: OpKey):
    return k[1]


def key_names(l: list):  # noqa: E741
    return list(map(lambda t: t[0], l))


def keys_of_name(s: str, l: list):  # noqa: E741
    filter(lambda t: t[0] == s, l)


def is_tag_node(t: tuple):
    return t[1] == 'tagNode'


def subdict_of_name(s: str, d: dict) -> dict:
    res = {}
    for t, v in d.items():
        if not isinstance(t, tuple):
            break
        if key_name(t) == s:
            res[t] = v

    return res


def next_keys(d: dict) -> list:
    key_set = set()
    for k in list(d.keys()):
        if isinstance(d[k], dict):
            key_set |= set(d[k].keys())
    return list(key_set)


def tuple_paths(d: dict) -> Iterator[list[tuple]]:
    def func(d, path):
        if isinstance(d, dict):
            if not d:
                yield path
            for k, v in d.items():
                if isinstance(k, tuple) and key_name(k) != '__node_data':
                    for r in func(v, path + [k]):
                        yield r
                else:
                    yield path
        else:
            yield path

    for r in func(d, []):
        yield r


def match_tuple_paths(
    path: list[str], paths: list[list[tuple[str, str]]]
) -> list[list[tuple[str, str]]]:
    return list(filter(lambda p: key_names(p) == path, paths))


def get_node_data(d: dict) -> NodeData:
    return d.get(('__node_data', None), {})


def get_node_data_at_path(d: dict, tpath):
    if not tpath:
        return {}
    # operates on actual paths, not names:
    if not isinstance(tpath[0], tuple):
        raise ValueError('must be path of tuples')
    while tpath and d:
        d = d.get(tpath[0], {})
        tpath = tpath[1:]

    return get_node_data(d)


def node_data_difference(a: NodeData, b: NodeData):
    out = ''
    for fld in fields(NodeData):
        if fld.name in ('children', 'files'):
            continue
        a_fld = getattr(a, fld.name)
        b_fld = getattr(b, fld.name)
        if a_fld != b_fld:
            out += f'prev: {a.files[-1:]} {a.path} {fld.name}: {a_fld}\n'
            out += f'new:  {b.files[-1:]} {b.path} {fld.name}: {b_fld}\n'
            out += '\n'

    return out


def collapse(d: OpData, acc: dict = None) -> tuple[dict, str, bool]:
    err = False
    inner_err = False
    out = ''
    inner_out = ''
    if acc is None:
        acc = {}
    if not isinstance(d, dict):
        return d
    for k, v in d.items():
        if isinstance(k, tuple):
            name = key_name(k)
            if name != '__node_data':
                new_data = get_node_data(v)
                if name in list(acc.keys()):
                    err = True
                    prev_data = acc[name].get('__node_data', {})
                    if prev_data:
                        out += f'prev: {prev_data["file"]} {prev_data["path"]}\n'
                    else:
                        out += '\n'
                    out += f'new: {new_data.file} {new_data.path}\n\n'
                else:
                    new_data.children = list(map(lambda t: t[0], new_data.children))
                    acc[name] = {}
                    acc[name]['__node_data'] = asdict(new_data)
                    inner, o, e = collapse(v)
                    inner_err |= e
                    inner_out += o
                    acc[name].update(inner)
        else:
            name = k
            acc[name] = v

    err |= inner_err
    out += inner_out

    return acc, out, err


class OpXml:
    def __init__(self):
        self.op_ref = {}

    def define(self, op_ref: dict) -> None:
        self.op_ref = op_ref

    def walk(self, func):
        def walk_op_data(obj, func):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(k, tuple):
                        res = func(k, v)
                        yield res
                    yield from walk_op_data(v, func)

        return walk_op_data(self.op_ref, func)

    @staticmethod
    def get_node_data_func(k, v):
        if key_name(k) == '__node_data':
            return v
        return None

    def walk_node_data(self):
        return filterfalse(lambda x: x is None, self.walk(self.get_node_data_func))

    def lookup(
        self, path: list[str], tag_values: bool = False, last_node_type: str = ''
    ) -> (OpData, list[str]):
        path = path[:]

        ref_path = []

        def prune_tree(d: dict, p: list[str]):
            p = p[:]
            if not d or not isinstance(d, dict) or not p:
                return d
            op_data: dict = subdict_of_name(p[0], d)
            op_keys = list(op_data.keys())
            ref_path.append(p[0])
            if len(p) < 2:
                # check last node_type
                if last_node_type:
                    keys = list(filter(lambda t: t[1] == last_node_type, op_keys))
                    values = list(map(lambda t: op_data[t], keys))
                    return dict(zip(keys, values))
                return op_data

            if p[1] not in key_names(next_keys(op_data)):
                # check if tag_values
                if tag_values:
                    p = p[2:]
                    keys = list(filter(is_tag_node, op_keys))
                    values = list(map(lambda t: prune_tree(op_data[t], p), keys))
                    return dict(zip(keys, values))
                return {}

            p = p[1:]
            op_data = list(map(lambda t: prune_tree(op_data[t], p), op_keys))

            return dict(zip(op_keys, op_data))

        return prune_tree(self.op_ref, path), ref_path

    def lookup_node_data(
        self, path: list[str], tag_values: bool = False, last_node_type: str = ''
    ) -> list[NodeData]:
        res = []
        d, ref_path = self.lookup(path, tag_values, last_node_type)
        paths = list(tuple_paths(d))
        paths = match_tuple_paths(ref_path, paths)
        for p in paths:
            res.append(get_node_data_at_path(d, p))

        return res
