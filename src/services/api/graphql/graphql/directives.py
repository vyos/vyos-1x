from ariadne import SchemaDirectiveVisitor, ObjectType
from . mutations import make_configure_resolver, make_config_file_resolver

class ConfigureDirective(SchemaDirectiveVisitor):
    """
    Class providing implementation of 'configure' directive in schema.

    """
    def visit_field_definition(self, field, object_type):
        name = f'{field.type}'
        # field.type contains the return value of the mutation; trim value
        # to produce canonical name
        name = name.replace('Result', '', 1)

        func = make_configure_resolver(name)
        field.resolve = func
        return field

class ConfigFileDirective(SchemaDirectiveVisitor):
    """
    Class providing implementation of 'configfile' directive in schema.

    """
    def visit_field_definition(self, field, object_type):
        name = f'{field.type}'
        # field.type contains the return value of the mutation; trim value
        # to produce canonical name
        name = name.replace('Result', '', 1)

        func = make_config_file_resolver(name)
        field.resolve = func
        return field

directives_dict = {"configure": ConfigureDirective, "configfile": ConfigFileDirective}
