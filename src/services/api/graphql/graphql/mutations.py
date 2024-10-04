# Copyright 2021-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

# used below by func_sig
from typing import Any, Dict, Optional  # pylint: disable=W0611 # noqa: F401
from graphql import GraphQLResolveInfo  # pylint: disable=W0611 # noqa: F401

from ariadne import ObjectType, convert_camel_case_to_snake
from makefun import with_signature

from vyos.opmode import Error as OpModeError

from ...session import SessionState
from ..libs import key_auth
from ..session.session import Session
from ..session.errors.op_mode_errors import op_mode_err_msg, op_mode_err_code

mutation = ObjectType('Mutation')


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
    func_sig = '(obj: Any, info: GraphQLResolveInfo, data: Optional[Dict]=None)'
    state = SessionState()

    @mutation.field(mutation_name)
    @with_signature(func_sig, func_name=resolver_name)
    async def func_impl(*args, **kwargs):
        try:
            auth_type = state.auth_type

            if auth_type == 'key':
                data = kwargs['data']
                key = data['key']

                auth = key_auth.auth_required(key)
                if auth is None:
                    return {'success': False, 'errors': ['invalid API key']}

                # We are finished with the 'key' entry, and may remove so as to
                # pass the rest of data (if any) to function.
                del data['key']

            elif auth_type == 'token':
                data = kwargs['data']
                if data is None:
                    data = {}
                info = kwargs['info']
                user = info.context.get('user')
                if user is None:
                    error = info.context.get('error')
                    if error is not None:
                        return {'success': False, 'errors': [error]}
                    return {'success': False, 'errors': ['not authenticated']}
            else:
                # AtrributeError will have already been raised if no
                # auth_type; validation and defaultValue ensure it is
                # one of the previous cases, so this is never reached.
                pass

            session = state.session

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

            return {'success': True, 'data': data}
        except OpModeError as e:
            typename = type(e).__name__
            msg = str(e)
            return {
                'success': False,
                'errore': ['op_mode_error'],
                'op_mode_error': {
                    'name': f'{typename}',
                    'message': msg if msg else op_mode_err_msg.get(typename, 'Unknown'),
                    'vyos_code': op_mode_err_code.get(typename, 9999),
                },
            }
        except Exception as error:
            return {'success': False, 'errors': [repr(error)]}

    return func_impl


def make_config_session_mutation_resolver(mutation_name):
    return make_mutation_resolver(
        mutation_name, mutation_name, convert_camel_case_to_snake(mutation_name)
    )


def make_gen_op_mutation_resolver(mutation_name):
    return make_mutation_resolver(mutation_name, mutation_name, 'gen_op_mutation')


def make_composite_mutation_resolver(mutation_name):
    return make_mutation_resolver(
        mutation_name, mutation_name, convert_camel_case_to_snake(mutation_name)
    )
