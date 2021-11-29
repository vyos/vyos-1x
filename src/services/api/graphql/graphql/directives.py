from ariadne import SchemaDirectiveVisitor, ObjectType
from . mutations import *

def non(arg):
    pass

class VyosDirective(SchemaDirectiveVisitor):
    def visit_field_definition(self, field, object_type, make_resolver=non):
        name = f'{field.type}'
        # field.type contains the return value of the mutation; trim value
        # to produce canonical name
        name = name.replace('Result', '', 1)

        func = make_resolver(name)
        field.resolve = func
        return field


class ConfigureDirective(VyosDirective):
    """
    Class providing implementation of 'configure' directive in schema.
    """
    def visit_field_definition(self, field, object_type):
        super().visit_field_definition(field, object_type,
                                       make_resolver=make_configure_resolver)

class ShowConfigDirective(VyosDirective):
    """
    Class providing implementation of 'show' directive in schema.
    """
    def visit_field_definition(self, field, object_type):
        super().visit_field_definition(field, object_type,
                                       make_resolver=make_show_config_resolver)

class ConfigFileDirective(VyosDirective):
    """
    Class providing implementation of 'configfile' directive in schema.
    """
    def visit_field_definition(self, field, object_type):
        super().visit_field_definition(field, object_type,
                                       make_resolver=make_config_file_resolver)

class ShowDirective(VyosDirective):
    """
    Class providing implementation of 'show' directive in schema.
    """
    def visit_field_definition(self, field, object_type):
        super().visit_field_definition(field, object_type,
                                       make_resolver=make_show_resolver)

directives_dict = {"configure": ConfigureDirective,
                   "showconfig": ShowConfigDirective,
                   "configfile": ConfigFileDirective,
                   "show": ShowDirective}
