#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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
#
#

import sys
import json
import argparse
from os.path import join
from os.path import abspath
from os.path import dirname
from xmltodict import parse

_here = dirname(__file__)

sys.path.append(join(_here, '..'))
from configtree import reference_tree_to_json, ConfigTreeError

xml_cache = abspath(join(_here, 'cache.py'))
xml_cache_json = 'xml_cache.json'
xml_tmp = join('/tmp', xml_cache_json)

node_data_fields = ("node_type", "multi", "valueless", "default_value")

def trim_node_data(cache: dict):
    for k in list(cache):
        if k == "node_data":
            for l in list(cache[k]):
                if l not in node_data_fields:
                    del cache[k][l]
        else:
            if isinstance(cache[k], dict):
                trim_node_data(cache[k])

def main():
    parser = argparse.ArgumentParser(description='generate and save dict from xml defintions')
    parser.add_argument('--xml-dir', type=str, required=True,
                        help='transcluded xml interface-definition directory')
    parser.add_argument('--save-json-dir', type=str,
                        help='directory to save json cache if needed')
    args = parser.parse_args()

    xml_dir = abspath(args.xml_dir)
    save_dir = abspath(args.save_json_dir) if args.save_json_dir else None

    try:
        reference_tree_to_json(xml_dir, xml_tmp)
    except ConfigTreeError as e:
        print(e)
        sys.exit(1)

    with open(xml_tmp) as f:
        d = json.loads(f.read())

    trim_node_data(d)

    if save_dir is not None:
        save_file = join(save_dir, xml_cache_json)
        with open(save_file, 'w') as f:
            f.write(json.dumps(d))

    syntax_version = join(xml_dir, 'xml-component-version.xml')
    with open(syntax_version) as f:
        content = f.read()

    parsed = parse(content)
    converted = parsed['interfaceDefinition']['syntaxVersion']
    version = {}
    for i in converted:
        tmp = {i['@component']: i['@version']}
        version |= tmp

    version = {"component_version": version}

    d |= version

    with open(xml_cache, 'w') as f:
        f.write(f'reference = {str(d)}')

if __name__ == '__main__':
    main()
