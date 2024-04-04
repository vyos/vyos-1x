# Copyright 2022-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

import datetime
from typing import Any
from typing import Dict
from ariadne import ObjectType
from graphql import GraphQLResolveInfo

from .. libs.token_auth import generate_token
from .. session.session import get_user_info
from .. import state

auth_token_mutation = ObjectType("Mutation")

@auth_token_mutation.field('AuthToken')
def auth_token_resolver(obj: Any, info: GraphQLResolveInfo, data: Dict):
    # non-nullable fields
    user = data['username']
    passwd = data['password']

    secret = state.settings['secret']
    exp_interval = int(state.settings['app'].state.vyos_token_exp)
    expiration = (datetime.datetime.now(tz=datetime.timezone.utc) +
                  datetime.timedelta(seconds=exp_interval))

    res = generate_token(user, passwd, secret, expiration)
    try:
        res |= get_user_info(user)
    except ValueError:
        # non-existent user already caught
        pass
    if 'token' in res:
        data['result'] = res
        return {
            "success": True,
            "data": data
        }

    if 'errors' in res:
        return {
            "success": False,
            "errors": res['errors']
        }

    return {
        "success": False,
        "errors": ['token generation failed']
    }
