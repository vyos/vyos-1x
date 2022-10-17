# Copyright 2021-2022 VyOS maintainers and contributors <maintainers@vyos.io>
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

from importlib import import_module
from typing import Any, Dict
from ariadne import ObjectType, convert_kwargs_to_snake_case, convert_camel_case_to_snake
from graphql import GraphQLResolveInfo
from makefun import with_signature

from .. import state
from .. import key_auth
from api.graphql.session.session import Session
from api.graphql.session.errors.op_mode_errors import op_mode_err_msg, op_mode_err_code
from vyos.opmode import Error as OpModeError

mutation = ObjectType("Mutation")

def make_mutation_resolver(mutation_name, class_name, session_func):
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
            key = data['key']

            auth = key_auth.auth_required(key)
            if auth is None:
                return {
                     "success": False,
                     "errors": ['invalid API key']
                }

            # We are finished with the 'key' entry, and may remove so as to
            # pass the rest of data (if any) to function.
            del data['key']

            session = state.settings['app'].state.vyos_session

            # one may override the session functions with a local subclass
            try:
                mod = import_module(f'api.graphql.session.override.{func_base_name}')
                klass = getattr(mod, class_name)
            except ImportError:
                # otherwise, dynamically generate subclass to invoke subclass
                # name based functions
                klass = type(class_name, (Session,), {})
            k = klass(session, data)
            method = getattr(k, session_func)
            result = method()
            data['result'] = result

            return {
                "success": True,
                "data": data
            }
        except OpModeError as e:
            typename = type(e).__name__
            msg = str(e)
            return {
                "success": False,
                "errore": ['op_mode_error'],
                "op_mode_error": {"name": f"{typename}",
                                 "message": msg if msg else op_mode_err_msg.get(typename, "Unknown"),
                                 "vyos_code": op_mode_err_code.get(typename, 9999)}
            }
        except Exception as error:
            return {
                "success": False,
                "errors": [repr(error)]
            }

    return func_impl

def make_config_session_mutation_resolver(mutation_name):
    return make_mutation_resolver(mutation_name, mutation_name,
                                  convert_camel_case_to_snake(mutation_name))

def make_gen_op_mutation_resolver(mutation_name):
    return make_mutation_resolver(mutation_name, mutation_name, 'gen_op_mutation')

def make_composite_mutation_resolver(mutation_name):
    return make_mutation_resolver(mutation_name, mutation_name,
                                  convert_camel_case_to_snake(mutation_name))
