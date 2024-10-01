# Copyright 2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

# pylint: disable=import-outside-toplevel


import typing

from ariadne.asgi import GraphQL
from starlette.middleware.cors import CORSMiddleware


if typing.TYPE_CHECKING:
    from fastapi import FastAPI


def graphql_init(app: 'FastAPI'):
    from ..session import SessionState
    from .libs.token_auth import get_user_context

    state = SessionState()

    # import after initializaion of state
    from .bindings import generate_schema

    schema = generate_schema()

    in_spec = state.introspection

    # remove route and reinstall below, for any changes; alternatively, test
    # for config_diff before proceeding
    graphql_clear(app)

    if state.origins:
        origins = state.origins
        app.add_route(
            '/graphql',
            CORSMiddleware(
                GraphQL(
                    schema,
                    context_value=get_user_context,
                    debug=True,
                    introspection=in_spec,
                ),
                allow_origins=origins,
                allow_methods=('GET', 'POST', 'OPTIONS'),
                allow_headers=('Authorization',),
            ),
        )
    else:
        app.add_route(
            '/graphql',
            GraphQL(
                schema,
                context_value=get_user_context,
                debug=True,
                introspection=in_spec,
            ),
        )


def graphql_clear(app: 'FastAPI'):
    for r in app.routes:
        if r.path == '/graphql':
            app.routes.remove(r)
