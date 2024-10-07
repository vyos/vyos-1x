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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import os
from typing import TYPE_CHECKING

from vyos.defaults import directories

# https://peps.python.org/pep-0484/#forward-references
if TYPE_CHECKING:
    from vyos.configtree import ConfigTree

config_file = os.path.join(directories['config'], 'config.boot')

def read_saved_value(path: list):
    if not isinstance(path, list) or not path:
        return ''
    from vyos.configtree import ConfigTree
    try:
        with open(config_file) as f:
            config_string = f.read()
        ct = ConfigTree(config_string)
    except Exception:
        return ''
    if not ct.exists(path):
        return ''
    res = ct.return_values(path)
    if len(res) == 1:
        return res[0]
    res = ct.list_nodes(path)
    if len(res) == 1:
        return ' '.join(res)
    return res

def flag(l: list) -> list:
    res = [l[0:i] for i,_ in enumerate(l, start=1)]
    return res

def tag_node_of_path(p: list) -> list:
    from vyos.xml_ref import is_tag

    fl = flag(p)
    res = list(map(is_tag, fl))

    return res

def set_tags(ct: 'ConfigTree', path: list) -> None:
    fl = flag(path)
    if_tag = tag_node_of_path(path)
    for condition, target in zip(if_tag, fl):
        if condition:
            ct.set_tag(target)

def parse_commands(cmds: str) -> dict:
    from re import split as re_split
    from shlex import split as shlex_split

    from vyos.xml_ref import definition
    from vyos.xml_ref.pkg_cache.vyos_1x_cache import reference

    ref_tree = definition.Xml()
    ref_tree.define(reference)

    res = []

    cmds = re_split(r'\n+', cmds)
    for c in cmds:
        cmd_parts = shlex_split(c)

        if not cmd_parts:
            # Ignore empty lines
            continue

        path = cmd_parts[1:]
        op = cmd_parts[0]

        try:
            path, value = ref_tree.split_path(path)
        except ValueError as e:
            raise ValueError(f'Incorrect command: {e}')

        entry = {}
        entry["op"] = op
        entry["path"] = path
        entry["value"] = value

        entry["is_multi"] = ref_tree.is_multi(path)
        entry["is_leaf"] = ref_tree.is_leaf(path)
        entry["is_tag"] = ref_tree.is_tag(path)

        res.append(entry)

    return res
