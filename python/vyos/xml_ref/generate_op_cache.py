#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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

import re
import sys
import json
import glob

from argparse import ArgumentParser
from os.path import join
from os.path import abspath
from os.path import dirname
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element
from typing import TypeAlias
from typing import Optional

_here = dirname(__file__)

sys.path.append(join(_here, '..'))
from defaults import directories

from op_definition import NodeData
from op_definition import PathData

xml_op_cache_json = 'xml_op_cache.json'
xml_op_tmp = join('/tmp', xml_op_cache_json)
op_ref_cache = abspath(join(_here, 'op_cache.py'))

OptElement: TypeAlias = Optional[Element]
DEBUG = False


def translate_exec(s: str) -> str:
    s = s.replace('${vyos_op_scripts_dir}', directories['op_mode'])
    s = s.replace('${vyos_libexec_dir}', directories['base'])
    return s


def translate_position(s: str, pos: list[str]) -> str:
    pos = pos.copy()
    pat: re.Pattern = re.compile(r'(?:\")?\${?([0-9]+)}?(?:\")?')
    t: str = pat.sub(r'_place_holder_\1_', s)

    # preferred to .format(*list) to avoid collisions with braces
    for i, p in enumerate(pos):
        t = t.replace(f'_place_holder_{i+1}_', p)

    return t


def translate_command(s: str, pos: list[str]) -> str:
    s = translate_exec(s)
    s = translate_position(s, pos)
    return s


def translate_op_script(s: str) -> str:
    s = s.replace('${vyos_completion_dir}', directories['completion_dir'])
    s = s.replace('${vyos_op_scripts_dir}', directories['op_mode'])
    return s


def insert_node(n: Element, l: list[PathData], path = None) -> None:
    # pylint: disable=too-many-locals,too-many-branches
    prop: OptElement = n.find('properties')
    children: OptElement = n.find('children')
    command: OptElement = n.find('command')
    # name is not None as required by schema
    name: str = n.get('name', 'schema_error')
    node_type: str = n.tag
    if path is None:
        path = []

    path.append(name)
    if node_type == 'tagNode':
        path.append(f'{name}-tag_value')

    help_prop: OptElement = None if prop is None else prop.find('help')
    help_text = None if help_prop is None else help_prop.text
    command_text = None if command is None else command.text
    if command_text is not None:
        command_text = translate_command(command_text, path)

    comp_help = None
    if prop is not None:
        che = prop.findall("completionHelp")
        for c in che:
            lists = c.findall("list")
            paths = c.findall("path")
            scripts = c.findall("script")

            comp_help = {}
            list_l = []
            for i in lists:
                list_l.append(i.text)
            path_l = []
            for i in paths:
                path_str = re.sub(r'\s+', '/', i.text)
                path_l.append(path_str)
            script_l = []
            for i in scripts:
                script_str = translate_op_script(i.text)
                script_l.append(script_str)

            comp_help['list'] = list_l
            comp_help['fs_path'] = path_l
            comp_help['script'] = script_l

    for d in l:
        if name in list(d):
            break
    else:
        d = {}
        l.append(d)

    inner_l = d.setdefault(name, [])

    inner_d: PathData = {'node_data': NodeData(node_type=node_type,
                                               help_text=help_text,
                                               comp_help=comp_help,
                                               command=command_text,
                                               path=path)}
    inner_l.append(inner_d)

    if children is not None:
        inner_nodes = children.iterfind("*")
        for inner_n in inner_nodes:
            inner_path = path[:]
            insert_node(inner_n, inner_l, inner_path)


def parse_file(file_path, l):
    tree = ET.parse(file_path)
    root = tree.getroot()
    for n in root.iterfind("*"):
        insert_node(n, l)


def main():
    parser = ArgumentParser(description='generate dict from xml defintions')
    parser.add_argument('--xml-dir', type=str, required=True,
                        help='transcluded xml op-mode-definition file')

    args = vars(parser.parse_args())

    xml_dir = abspath(args['xml_dir'])

    l = []

    for fname in glob.glob(f'{xml_dir}/*.xml'):
        parse_file(fname, l)

    with open(xml_op_tmp, 'w') as f:
        json.dump(l, f, indent=2)

    with open(op_ref_cache, 'w') as f:
        f.write(f'op_reference = {str(l)}')

if __name__ == '__main__':
    main()
