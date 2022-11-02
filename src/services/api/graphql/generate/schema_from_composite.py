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
import sys
import json
from inspect import signature, getmembers, isfunction, isclass, getmro
from jinja2 import Template

from vyos.defaults import directories
if __package__ is None or __package__ == '':
    sys.path.append("/usr/libexec/vyos/services/api")
    from graphql.libs.op_mode import snake_to_pascal_case, map_type_name
    from composite_function import queries, mutations
    from vyos.config import Config
    from vyos.configdict import dict_merge
    from vyos.xml import defaults
else:
    from .. libs.op_mode import snake_to_pascal_case, map_type_name
    from . composite_function import queries, mutations
    from .. import state

SCHEMA_PATH = directories['api_schema']

if __package__ is None or __package__ == '':
    # allow running stand-alone
    conf = Config()
    base = ['service', 'https', 'api']
    graphql_dict = conf.get_config_dict(base, key_mangling=('-', '_'),
                                          no_tag_node_value_mangle=True,
                                          get_first_key=True)
    if 'graphql' not in graphql_dict:
        exit("graphql is not configured")

    graphql_dict = dict_merge(defaults(base), graphql_dict)
    auth_type = graphql_dict['graphql']['authentication']['type']
else:
    auth_type = state.settings['app'].state.vyos_auth_type

schema_data: dict = {'auth_type': auth_type,
                     'schema_name': '',
                     'schema_fields': []}

query_template  = """
{%- if auth_type == 'key' %}
input {{ schema_name }}Input {
    key: String!
    {%- for field_entry in schema_fields %}
    {{ field_entry }}
    {%- endfor %}
}
{%- elif schema_fields %}
input {{ schema_name }}Input {
    {%- for field_entry in schema_fields %}
    {{ field_entry }}
    {%- endfor %}
}
{%- endif %}

type {{ schema_name }} {
    result: Generic
}

type {{ schema_name }}Result {
    data: {{ schema_name }}
    success: Boolean!
    errors: [String]
}

extend type Query {
{%- if auth_type == 'key' or schema_fields %}
    {{ schema_name }}(data: {{ schema_name }}Input) : {{ schema_name }}Result @compositequery
{%- else %}
    {{ schema_name }} : {{ schema_name }}Result @compositequery
{%- endif %}
}
"""

mutation_template  = """
{%- if auth_type == 'key' %}
input {{ schema_name }}Input {
    key: String!
    {%- for field_entry in schema_fields %}
    {{ field_entry }}
    {%- endfor %}
}
{%- elif schema_fields %}
input {{ schema_name }}Input {
    {%- for field_entry in schema_fields %}
    {{ field_entry }}
    {%- endfor %}
}
{%- endif %}

type {{ schema_name }} {
    result: Generic
}

type {{ schema_name }}Result {
    data: {{ schema_name }}
    success: Boolean!
    errors: [String]
}

extend type Mutation {
{%- if auth_type == 'key' or schema_fields %}
    {{ schema_name }}(data: {{ schema_name }}Input) : {{ schema_name }}Result @compositemutation
{%- else %}
    {{ schema_name }} : {{ schema_name }}Result @compositemutation
{%- endif %}
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
