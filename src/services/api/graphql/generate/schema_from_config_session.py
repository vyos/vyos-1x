#!/usr/bin/env python3
#
# Copyright (C) 2022-2023 VyOS maintainers and contributors
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
# A utility to generate GraphQL schema defintions from typing information of
# (wrappers of) native configsession functions.

import os
import sys
from inspect import signature
from jinja2 import Template

from vyos.defaults import directories
if __package__ is None or __package__ == '':
    sys.path.append(os.path.join(directories['services'], 'api'))
    from graphql.libs.op_mode import snake_to_pascal_case, map_type_name
    from config_session_function import queries, mutations
else:
    from .. libs.op_mode import snake_to_pascal_case, map_type_name
    from . config_session_function import queries, mutations

SCHEMA_PATH = directories['api_schema']
CLIENT_OP_PATH = directories['api_client_op']

schema_data: dict = {'schema_name': '',
                     'schema_fields': []}

query_template  = """
input {{ schema_name }}Input {
    key: String
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
    {{ schema_name }}(data: {{ schema_name }}Input) : {{ schema_name }}Result @configsessionquery
}
"""

mutation_template  = """
input {{ schema_name }}Input {
    key: String
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
    {{ schema_name }}(data: {{ schema_name }}Input) : {{ schema_name }}Result @configsessionmutation
}
"""

op_query_template = """
query {{ op_name }} ({{ op_sig }}) {
  {{ op_name }} (data: { {{ op_arg }} }) {
    success
    errors
    data {
      result
    }
  }
}
"""

op_mutation_template = """
mutation {{ op_name }} ({{ op_sig }}) {
  {{ op_name }} (data: { {{ op_arg }} }) {
    success
    errors
    data {
      result
    }
  }
}
"""

def create_schema(func_name: str, func: callable, template: str) -> str:
    sig = signature(func)

    field_dict = {}
    for k in sig.parameters:
        field_dict[sig.parameters[k].name] = map_type_name(sig.parameters[k].annotation)

    schema_fields = []
    for k,v in field_dict.items():
        schema_fields.append(k+': '+v)

    schema_data['schema_name'] = snake_to_pascal_case(func_name)
    schema_data['schema_fields'] = schema_fields

    j2_template = Template(template)
    res = j2_template.render(schema_data)

    return res

def create_client_op(func_name: str, func: callable, template: str) -> str:
    sig = signature(func)

    field_dict = {}
    for k in sig.parameters:
        field_dict[sig.parameters[k].name] = map_type_name(sig.parameters[k].annotation)

    op_sig = ['$key: String']
    op_arg = ['key: $key']
    for k,v in field_dict.items():
        op_sig.append('$'+k+': '+v)
        op_arg.append(k+': $'+k)

    op_data = {}
    op_data['op_name'] = snake_to_pascal_case(func_name)
    op_data['op_sig'] = ', '.join(op_sig)
    op_data['op_arg'] = ', '.join(op_arg)

    j2_template = Template(template)

    res = j2_template.render(op_data)

    return res

def generate_config_session_definitions():
    schema = []
    client_op = []
    for name,func in queries.items():
        res = create_schema(name, func, query_template)
        schema.append(res)
        res = create_client_op(name, func, op_query_template)
        client_op.append(res)

    for name,func in mutations.items():
        res = create_schema(name, func, mutation_template)
        schema.append(res)
        res = create_client_op(name, func, op_mutation_template)
        client_op.append(res)

    out = '\n'.join(schema)
    with open(f'{SCHEMA_PATH}/configsession.graphql', 'w') as f:
        f.write(out)

    out = '\n'.join(client_op)
    with open(f'{CLIENT_OP_PATH}/configsession.graphql', 'w') as f:
        f.write(out)

if __name__ == '__main__':
    generate_config_session_definitions()
