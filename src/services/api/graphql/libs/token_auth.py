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


import jwt
import uuid
import pam
from secrets import token_hex

from ...session import SessionState


def _check_passwd_pam(username: str, passwd: str) -> bool:
    if pam.authenticate(username, passwd):
        return True
    return False


def init_secret():
    state = SessionState()
    length = int(state.secret_len)
    secret = token_hex(length)
    state.secret = secret


def generate_token(user: str, passwd: str, secret: str, exp: int) -> dict:
    if user is None or passwd is None:
        return {}
    state = SessionState()
    if _check_passwd_pam(user, passwd):
        try:
            users = state.token_users
        except AttributeError:
            users = state.token_users = {}
        user_id = uuid.uuid1().hex
        payload_data = {'iss': user, 'sub': user_id, 'exp': exp}
        secret = getattr(state, 'secret', None)
        if secret is None:
            return {'errors': ['missing secret']}
        token = jwt.encode(payload=payload_data, key=secret, algorithm='HS256')

        users |= {user_id: user}
        return {'token': token}
    else:
        return {'errors': ['failed pam authentication']}


def get_user_context(request):
    context = {}
    context['request'] = request
    context['user'] = None
    state = SessionState()
    if 'Authorization' in request.headers:
        auth = request.headers['Authorization']
        scheme, token = auth.split()
        if scheme.lower() != 'bearer':
            return context

        try:
            secret = getattr(state, 'secret', None)
            payload = jwt.decode(token, secret, algorithms=['HS256'])
            user_id: str = payload.get('sub')
            if user_id is None:
                return context
        except jwt.exceptions.ExpiredSignatureError:
            context['error'] = 'expired token'
            return context
        except jwt.PyJWTError:
            return context
        try:
            users = state.token_users
        except AttributeError:
            return context

        user = users.get(user_id)
        if user is not None:
            context['user'] = user

    return context
