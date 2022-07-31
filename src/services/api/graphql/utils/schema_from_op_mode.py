#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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
# A utility to generate GraphQL schema defintions from standardized op-mode
# scripts.

import os
import json
import typing
from inspect import signature, getmembers, isfunction
from jinja2 import Template

from vyos.defaults import directories
from . util import load_as_module, is_op_mode_function_name, is_show_function_name

OP_MODE_PATH = directories['op_mode']
SCHEMA_PATH = directories['api_schema']
DATA_DIR = directories['data']

op_mode_include_file = os.path.join(DATA_DIR, 'op-mode-standardized.json')

schema_data: dict = {'schema_name': '',
                     'schema_fields': []}

query_template  = """
input {{ schema_name }}Input {
    key: String!
    {%- for field_entry in schema_fields %}
    {{ field_entry }}
    {%- endfor %}
}

type {{ schema_name }} {
    result: Generic
}

type {{ schema_name }}Result {
    data: {{ schema_name }}
    success: Boolean!
    errors: [String]
}

extend type Query {
    {{ schema_name }}(data: {{ schema_name }}Input) : {{ schema_name }}Result @genopquery
}
"""

mutation_template  = """
input {{ schema_name }}Input {
    key: String!
    {%- for field_entry in schema_fields %}
    {{ field_entry }}
    {%- endfor %}
}

type {{ schema_name }} {
    result: Generic
}

type {{ schema_name }}Result {
    data: {{ schema_name }}
    success: Boolean!
    errors: [String]
}

extend type Mutation {
    {{ schema_name }}(data: {{ schema_name }}Input) : {{ schema_name }}Result @genopmutation
}
"""

def _snake_to_pascal_case(name: str) -> str:
    res = ''.join(map(str.title, name.split('_')))
    return res

def _map_type_name(type_name: type, optional: bool = False) -> str:
    if type_name == str:
        return 'String!' if not optional else 'String = null'
    if type_name == int:
        return 'Int!' if not optional else 'Int = null'
    if type_name == bool:
        return 'Boolean!' if not optional else 'Boolean = false'
    if typing.get_origin(type_name) == list:
        if not optional:
            return f'[{_map_type_name(typing.get_args(type_name)[0])}]!'
        return f'[{_map_type_name(typing.get_args(type_name)[0])}]'
    # typing.Optional is typing.Union[_, NoneType]
    if (typing.get_origin(type_name) is typing.Union and
            typing.get_args(type_name)[1] == type(None)):
        return f'{_map_type_name(typing.get_args(type_name)[0], optional=True)}'

    # scalar 'Generic' is defined in schema.graphql
    return 'Generic'

def create_schema(func_name: str, base_name: str, func: callable) -> str:
    sig = signature(func)

    field_dict = {}
    for k in sig.parameters:
        field_dict[sig.parameters[k].name] = _map_type_name(sig.parameters[k].annotation)

    # It is assumed that if one is generating a schema for a 'show_*'
    # function, that 'get_raw_data' is present and 'raw' is desired.
    if 'raw' in list(field_dict):
        del field_dict['raw']

    schema_fields = []
    for k,v in field_dict.items():
        schema_fields.append(k+': '+v)

    schema_data['schema_name'] = _snake_to_pascal_case(func_name + '_' + base_name)
    schema_data['schema_fields'] = schema_fields

    if is_show_function_name(func_name):
        j2_template = Template(query_template)
    else:
        j2_template = Template(mutation_template)

    res = j2_template.render(schema_data)

    return res

def generate_op_mode_definitions():
    with open(op_mode_include_file) as f:
        op_mode_files = json.load(f)

    for file in op_mode_files:
        basename = os.path.splitext(file)[0].replace('-', '_')
        module = load_as_module(basename, os.path.join(OP_MODE_PATH, file))

        funcs = getmembers(module, isfunction)
        funcs = list(filter(lambda ft: is_op_mode_function_name(ft[0]), funcs))

        funcs_dict = {}
        for (name, thunk) in funcs:
            funcs_dict[name] = thunk

        results = []
        for name,func in funcs_dict.items():
            res = create_schema(name, basename, func)
            results.append(res)

        out = '\n'.join(results)
        with open(f'{SCHEMA_PATH}/{basename}.graphql', 'w') as f:
            f.write(out)

if __name__ == '__main__':
    generate_op_mode_definitions()
