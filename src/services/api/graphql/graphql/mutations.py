
from importlib import import_module
from typing import Any, Dict
from ariadne import ObjectType, convert_kwargs_to_snake_case, convert_camel_case_to_snake
from graphql import GraphQLResolveInfo
from makefun import with_signature

from .. import state
from api.graphql.recipes.session import Session

mutation = ObjectType("Mutation")

def make_resolver(mutation_name, class_name, session_func):
    """Dynamically generate a resolver for the mutation named in the
    schema by 'mutation_name'.

    Dynamic generation is provided using the package 'makefun' (via the
    decorator 'with_signature'), which provides signature-preserving
    function wrappers; it provides several improvements over, say,
    functools.wraps.

    :raise Exception:
        raising ConfigErrors, or internal errors
    """

    func_base_name = convert_camel_case_to_snake(class_name)
    resolver_name = f'resolve_{func_base_name}'
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

            # one may override the session functions with a local subclass
            try:
                mod = import_module(f'api.graphql.recipes.{func_base_name}')
                klass = getattr(mod, class_name)
            except ImportError:
                # otherwise, dynamically generate subclass to invoke subclass
                # name based templates
                klass = type(class_name, (Session,), {})
            k = klass(session, data)
            method = getattr(k, session_func)
            result = method()
            data['result'] = result

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

def make_configure_resolver(mutation_name):
    class_name = mutation_name
    return make_resolver(mutation_name, class_name, 'configure')

def make_config_file_resolver(mutation_name):
    if 'Save' in mutation_name:
        class_name = mutation_name.replace('Save', '', 1)
        return make_resolver(mutation_name, class_name, 'save')
    elif 'Load' in mutation_name:
        class_name = mutation_name.replace('Load', '', 1)
        return make_resolver(mutation_name, class_name, 'load')
    else:
        raise Exception

def make_show_resolver(mutation_name):
    class_name = mutation_name
    return make_resolver(mutation_name, class_name, 'show')
