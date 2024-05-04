#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
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

import sys
import json
from argparse import ArgumentParser
from argparse import ArgumentTypeError
from os.path import join
from os.path import abspath
from os.path import dirname
from xmltodict import parse

_here = dirname(__file__)

sys.path.append(join(_here, '..'))
from configtree import reference_tree_to_json, ConfigTreeError

xml_cache_json = 'xml_cache.json'
xml_tmp = join('/tmp', xml_cache_json)
pkg_cache = abspath(join(_here, 'pkg_cache'))
ref_cache = abspath(join(_here, 'cache.py'))

node_data_fields = ("node_type", "multi", "valueless", "default_value",
                    "owner", "priority")

def trim_node_data(cache: dict):
    for k in list(cache):
        if k == "node_data":
            for l in list(cache[k]):
                if l not in node_data_fields:
                    del cache[k][l]
        else:
            if isinstance(cache[k], dict):
                trim_node_data(cache[k])

def non_trivial(s):
    if not s:
        raise ArgumentTypeError("Argument must be non empty string")
    return s

def main():
    parser = ArgumentParser(description='generate and save dict from xml defintions')
    parser.add_argument('--xml-dir', type=str, required=True,
                        help='transcluded xml interface-definition directory')
    parser.add_argument('--package-name', type=non_trivial, default='vyos-1x',
                        help='name of current package')
    parser.add_argument('--output-path', help='path to generated cache')
    args = vars(parser.parse_args())

    xml_dir = abspath(args['xml_dir'])
    pkg_name = args['package_name'].replace('-','_')
    cache_name = pkg_name + '_cache.py'
    out_path = args['output_path']
    path = out_path if out_path is not None else pkg_cache
    xml_cache = abspath(join(path, cache_name))

    try:
        reference_tree_to_json(xml_dir, xml_tmp)
    except ConfigTreeError as e:
        print(e)
        sys.exit(1)

    with open(xml_tmp) as f:
        d = json.loads(f.read())

    trim_node_data(d)

    syntax_version = join(xml_dir, 'xml-component-version.xml')
    try:
        with open(syntax_version) as f:
            component = f.read()
    except FileNotFoundError:
        if pkg_name != 'vyos_1x':
            component = ''
        else:
            print("\nWARNING: missing xml-component-version.xml\n")
            sys.exit(1)

    if component:
        parsed = parse(component)
    else:
        parsed = None
    version = {}
    # addon package definitions may have empty (== 0) version info
    if parsed is not None and parsed['interfaceDefinition'] is not None:
        converted = parsed['interfaceDefinition']['syntaxVersion']
        if not isinstance(converted, list):
            converted = [converted]
        for i in converted:
            tmp = {i['@component']: i['@version']}
            version |= tmp

    version = {"component_version": version}

    d |= version

    with open(xml_cache, 'w') as f:
        f.write(f'reference = {str(d)}')

    print(cache_name)

if __name__ == '__main__':
    main()
