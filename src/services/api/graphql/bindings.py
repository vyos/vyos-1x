import vyos.defaults
from . graphql.mutations import mutation
from . graphql.directives import directives_dict
from ariadne import make_executable_schema, load_schema_from_path, snake_case_fallback_resolvers

def generate_schema():
    api_schema_dir = vyos.defaults.directories['api_schema']

    type_defs = load_schema_from_path(api_schema_dir)

    schema = make_executable_schema(type_defs, mutation, snake_case_fallback_resolvers, directives=directives_dict)

    return schema
