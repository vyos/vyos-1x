# Copyright 2021 VyOS maintainers and contributors <maintainers@vyos.io>
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

import vyos.defaults
from . graphql.queries import query
from . graphql.mutations import mutation
from . graphql.directives import directives_dict
from . graphql.errors import op_mode_error
from . utils.schema_from_op_mode import generate_op_mode_definitions
from ariadne import make_executable_schema, load_schema_from_path, snake_case_fallback_resolvers

def generate_schema():
    api_schema_dir = vyos.defaults.directories['api_schema']

    generate_op_mode_definitions()

    type_defs = load_schema_from_path(api_schema_dir)

    schema = make_executable_schema(type_defs, query, op_mode_error, mutation, snake_case_fallback_resolvers, directives=directives_dict)

    return schema
