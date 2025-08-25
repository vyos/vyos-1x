#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
import io
import re
import sys
import glob
import json
import atexit

from argparse import ArgumentParser
from os.path import join
from os.path import abspath
from os.path import dirname
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element
from functools import cmp_to_key
from typing import TypeAlias
from typing import Optional

from op_definition import NodeData
from op_definition import OpKey  # pylint: disable=unused-import # noqa: F401
from op_definition import OpData  # pylint: disable=unused-import # noqa: F401
from op_definition import key_name
from op_definition import key_type
from op_definition import node_data_difference
from op_definition import get_node_data
from op_definition import collapse

_here = dirname(__file__)

sys.path.append(join(_here, '..'))
# pylint: disable=wrong-import-position,wrong-import-order
from defaults import directories  # noqa: E402


op_ref_cache = abspath(join(_here, 'op_cache.py'))

OptElement: TypeAlias = Optional[Element]


# It is expected that the node_data help txt contained in top-level nodes,
# shared across files, e.g.'show', will reveal inconsistencies; to list
# differences, use --check-xml-consistency
CHECK_XML_CONSISTENCY = False
err_buf = io.StringIO()


def write_err_buf():
    err_buf.seek(0)
    out = err_buf.read()
    print(out)
    err_buf.close()


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
        t = t.replace(f'_place_holder_{i+1}_', f'{{{{{p}}}}}')

    return t


def translate_command(s: str, pos: list[str]) -> str:
    s = translate_exec(s)
    s = translate_position(s, pos)

    # If there are any untranslated occurences of '_place_holder_",
    # it means the command is incorrect,
    # e.g., it references "$6" when it only has five words.
    if re.search(r'_place_holder_', s):
        print(f'Command translation failed: {s}')
        sys.exit(1)

    return s


def translate_op_script(s: str) -> str:
    s = s.replace('${vyos_completion_dir}', directories['completion_dir'])
    s = s.replace('${vyos_op_scripts_dir}', directories['op_mode'])
    return s


def compare_keys(a, b):
    # pylint: disable=too-many-return-statements
    match key_type(a), key_type(b):
        case None, None:
            if key_name(a) == key_name(b):
                return 0
            return -1 if key_name(a) < key_name(b) else 1
        case None, _:
            return -1
        case _, None:
            return 1
        case _, _:
            if key_name(a) == key_name(b):
                if key_type(a) == key_type(b):
                    return 0
                return -1 if key_type(a) < key_type(b) else 1
            return -1 if key_name(a) < key_name(b) else 1


def sort_func(obj: dict, key_func):
    if not obj or not isinstance(obj, dict):
        return obj
    k_list = list(obj.keys())
    if not isinstance(k_list[0], tuple):
        return obj
    k_list = sorted(k_list, key=key_func)
    v_list = map(lambda t: sort_func(obj[t], key_func), k_list)
    return dict(zip(k_list, v_list))


def sort_op_data(obj):
    key_func = cmp_to_key(compare_keys)
    return sort_func(obj, key_func)


def insert_node(
    n: Element, d: dict, path: list[str] = None, parent: NodeData = None, file: str = ''
) -> None:
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    prop: OptElement = n.find('properties')
    children: OptElement = n.find('children')
    command: OptElement = n.find('command')
    standalone: OptElement = n.find('standalone')
    node_type: str = n.tag

    if node_type == 'virtualTagNode':
        name = '__virtual_tag'
    else:
        name = n.get('name')
        if not name:
            raise ValueError(
                'Node name is required for all node types except <virtualTagNode>'
            )

    if path is None:
        path = []

    if node_type != 'virtualTagNode':
        path.append(name)

    if node_type == 'tagNode':
        path.append(f'{name}-tag_value')

    if node_type == 'virtualTagNode':
        path.append(f'{parent.name}-tag_value')

    help_prop: OptElement = None if prop is None else prop.find('help')
    help_text = None if help_prop is None else help_prop.text
    command_text = None if command is None else command.text
    if command_text is not None:
        command_text = translate_command(command_text, path)

    try:
        standalone_command = translate_command(standalone.find('command').text, path)
    except AttributeError:
        standalone_command = None

    try:
        standalone_help_text = translate_command(standalone.find('help').text, path)
    except AttributeError:
        standalone_help_text = None

    comp_help = {}
    if prop is not None:
        che = prop.findall('completionHelp')

        for c in che:
            comp_list_els = c.findall('list')
            comp_path_els = c.findall('path')
            comp_script_els = c.findall('script')

            comp_lists = []
            for i in comp_list_els:
                comp_lists.append(i.text)

            comp_paths = []
            for i in comp_path_els:
                comp_paths.append(i.text)

            comp_scripts = []
            for i in comp_script_els:
                comp_script_str = translate_op_script(i.text)
                comp_scripts.append(comp_script_str)

            if comp_lists:
                comp_help['list'] = comp_lists
            if comp_paths:
                comp_help['path'] = comp_paths
            if comp_scripts:
                comp_help['script'] = comp_scripts

    new_node_data = NodeData()
    new_node_data.name = name
    new_node_data.node_type = node_type
    new_node_data.comp_help = comp_help
    new_node_data.help_text = help_text
    new_node_data.command = command_text
    new_node_data.standalone_help_text = standalone_help_text
    new_node_data.standalone_command = standalone_command
    new_node_data.path = path
    new_node_data.files = [file]

    value = {('__node_data', None): new_node_data}
    key = (name, node_type)

    cur_value = d.setdefault(key, value)

    if CHECK_XML_CONSISTENCY:
        out = node_data_difference(get_node_data(cur_value), get_node_data(value))
        if out:
            err_buf.write(out)

    # track the correct pointer reference:
    cur_node_data = cur_value[('__node_data', None)]

    if file not in cur_node_data.files:
        cur_node_data.files.append(file)

    if not cur_node_data.comp_help and comp_help:
        cur_node_data.comp_help = comp_help

    if not cur_node_data.help_text and help_text:
        cur_node_data.help_text = help_text

    if not cur_node_data.command and command_text:
        cur_node_data.command = command_text

    if not cur_node_data.standalone_help_text and standalone_help_text:
        cur_node_data.standalone_help_text = standalone_help_text

    if not cur_node_data.standalone_command and standalone_command:
        cur_node_data.standalone_command = standalone_command

    if parent and key not in parent.children:
        parent.children.append(key)

    if children is not None:
        inner_nodes = children.iterfind('*')
        for inner_n in inner_nodes:
            inner_path = path[:]
            insert_node(inner_n, d[key], inner_path, cur_node_data, file)


def parse_file(file_path, d):
    tree = ET.parse(file_path)
    root = tree.getroot()
    file = os.path.basename(file_path)
    for n in root.iterfind('*'):
        insert_node(n, d, file=file)


def main():
    # pylint: disable=global-statement
    global CHECK_XML_CONSISTENCY

    parser = ArgumentParser(description='generate dict from xml defintions')
    parser.add_argument(
        '--xml-dir',
        type=str,
        required=True,
        help='transcluded xml op-mode-definition file',
    )
    parser.add_argument(
        '--check-xml-consistency',
        action='store_true',
        help='check consistency of node data across files',
    )
    parser.add_argument(
        '--select',
        type=str,
        help='limit cache to a subset of XML files: "power_ctl | multicast-group | ..."',
    )

    parser.add_argument(
        '--export-json',
        type=str,
        help='Export a JSON version of the cache to a file',
    )

    args = vars(parser.parse_args())

    if args['check_xml_consistency']:
        CHECK_XML_CONSISTENCY = True
        atexit.register(write_err_buf)

    xml_dir = abspath(args['xml_dir'])

    op_mode_data = {}

    select = args['select']
    if select:
        select = [item.strip() for item in select.split('|')]

    for fname in sorted(glob.glob(f'{xml_dir}/*.xml')):
        file = os.path.basename(fname)
        if not select or os.path.splitext(file)[0] in select:
            parse_file(fname, op_mode_data)

    op_mode_data = sort_op_data(op_mode_data)

    res, out, err = collapse(op_mode_data)
    if err:
        print(
            'Failed to generate operational command definition cache due to duplicate paths.'
        )
        print('Found the following duplicate paths:\n')
        print(out)
        sys.exit(1)
    else:
        op_mode_data = res

    with open(op_ref_cache, 'w') as f:
        f.write('from vyos.xml_ref.op_definition import NodeData\n')
        f.write(f'op_reference = {str(op_mode_data)}')

    if args['export_json']:
        with open(args['export_json'], 'w') as f:
            json.dump(op_mode_data, f)


if __name__ == '__main__':
    main()
