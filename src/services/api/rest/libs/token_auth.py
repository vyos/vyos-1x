# Copyright (C) VyOS Inc.
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
import threading
from secrets import token_hex

import jwt

from ...session import SessionState

_secret_lock = threading.Lock()


def verify_oidc_token(token: str):
    """Validate an OIDC Bearer token against the configured OIDC issuer JWKS.

    Returns the subject identifier on success, None on failure.
    Requires set service https api rest authentication oidc issuer <url>.
    """
    state = SessionState()
    if not state.oidc_issuer:
        return None
    try:
        from jwt import PyJWKClient

        jwks_uri = (
            state.oidc_jwks_uri or f"{state.oidc_issuer}/protocol/openid-connect/certs"
        )
        jwks_client = PyJWKClient(jwks_uri, cache_keys=True)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
            options={"verify_aud": False},
            issuer=state.oidc_issuer,
            leeway=30,
        )
        return payload.get("sub") or payload.get("client_id") or "oidc-client"
    except Exception as e:
        print(f"OIDC token validation failed: {e}", flush=True)
        return None


def init_secret():
    state = SessionState()
    if state.rest_secret is not None:
        return
    length = int(state.rest_secret_len or 32)
    with _secret_lock:
        if state.rest_secret is None:
            state.rest_secret = token_hex(length)


def generate_token(key_id: str) -> dict:
    state = SessionState()
    init_secret()
    exp_interval = int(state.rest_token_exp or 3600)
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
