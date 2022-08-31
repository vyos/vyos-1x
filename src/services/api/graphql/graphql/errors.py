
from ariadne import InterfaceType

op_mode_error = InterfaceType("OpModeError")

@op_mode_error.type_resolver
def resolve_op_mode_error(obj, *_):
    return obj['name']
