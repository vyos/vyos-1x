# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
from secrets import token_hex

import jwt

from ...session import SessionState


def init_secret():
    state = SessionState()
    if state.rest_secret is not None:
        return
    length = state.rest_secret_len or 32
    state.rest_secret = token_hex(length)


def generate_token(key_id: str) -> dict:
    state = SessionState()
    init_secret()
    exp_interval = state.rest_token_exp or 3600
    expiration = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(
        seconds=exp_interval
    )
    payload = {'iss': 'vyos-rest-api', 'sub': key_id, 'exp': expiration}
    token = jwt.encode(payload=payload, key=state.rest_secret, algorithm='HS256')
    return {'token': token, 'expires_in': exp_interval}


def verify_token(token: str):
    state = SessionState()
    if state.rest_secret is None:
        return None
    try:
        payload = jwt.decode(token, state.rest_secret, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.PyJWTError:
        return None
    return payload.get('sub')
