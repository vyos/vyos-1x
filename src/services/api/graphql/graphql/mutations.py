
from importlib import import_module
from typing import Any, Dict
from ariadne import ObjectType, convert_kwargs_to_snake_case, convert_camel_case_to_snake
from graphql import GraphQLResolveInfo
from makefun import with_signature

from .. import state

mutation = ObjectType("Mutation")

def make_resolver(mutation_name):
    """Dynamically generate a resolver for the mutation named in the
    schema by 'mutation_name'.

    Dynamic generation is provided using the package 'makefun' (via the
    decorator 'with_signature'), which provides signature-preserving
    function wrappers; it provides several improvements over, say,
    functools.wraps.

    :raise Exception:
        encapsulating ConfigErrors, or internal errors
    """
    class_name = mutation_name.replace('create', '', 1).replace('delete', '', 1)
    func_base_name = convert_camel_case_to_snake(class_name)
    resolver_name = f'resolve_create_{func_base_name}'
    func_sig = '(obj: Any, info: GraphQLResolveInfo, data: Dict)'

    @mutation.field(mutation_name)
    @convert_kwargs_to_snake_case
    @with_signature(func_sig, func_name=resolver_name)
    async def func_impl(*args, **kwargs):
        try:
            if 'data' not in kwargs:
                return {
                    "success": False,
                    "errors": ['missing data']
                }

            data = kwargs['data']
            session = state.settings['app'].state.vyos_session

            mod = import_module(f'api.recipes.{func_base_name}')
            klass = getattr(mod, class_name)
            k = klass(session, data)
            k.configure()

            return {
                "success": True,
                "data": data
            }
        except Exception as error:
            return {
                "success": False,
                "errors": [str(error)]
            }

    return func_impl


