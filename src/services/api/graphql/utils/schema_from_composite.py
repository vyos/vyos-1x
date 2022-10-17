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
# A utility to generate GraphQL schema defintions from typing information of
# composite functions comprising several requests.

import os
import json
from inspect import signature, getmembers, isfunction, isclass, getmro
from jinja2 import Template

if __package__ is None or __package__ == '':
    from util import snake_to_pascal_case, map_type_name
else:
    from . util import snake_to_pascal_case, map_type_name

# this will be run locally before the build
SCHEMA_PATH = '../graphql/schema'

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
    {{ schema_name }}(data: {{ schema_name }}Input) : {{ schema_name }}Result @compositequery
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
    {{ schema_name }}(data: {{ schema_name }}Input) : {{ schema_name }}Result @compositemutation
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

def generate_composite_definitions():
    from composite_function import queries, mutations

    results = []
    for name,func in queries.items():
        res = create_schema(name, func, query_template)
        results.append(res)

    for name,func in mutations.items():
        res = create_schema(name, func, mutation_template)
        results.append(res)

    out = '\n'.join(results)
    with open(f'{SCHEMA_PATH}/composite.graphql', 'w') as f:
        f.write(out)

if __name__ == '__main__':
    generate_composite_definitions()
