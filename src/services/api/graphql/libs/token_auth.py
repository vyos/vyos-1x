import jwt
import uuid
import pam
from secrets import token_hex

from .. import state

def _check_passwd_pam(username: str, passwd: str) -> bool:
    if pam.authenticate(username, passwd):
        return True
    return False

def init_secret():
    length = int(state.settings['app'].state.vyos_secret_len)
    secret = token_hex(length)
    state.settings['secret'] = secret

def generate_token(user: str, passwd: str, secret: str, exp: int) -> dict:
    if user is None or passwd is None:
        return {}
    if _check_passwd_pam(user, passwd):
        app = state.settings['app']
        try:
            users = app.state.vyos_token_users
        except AttributeError:
            app.state.vyos_token_users = {}
            users = app.state.vyos_token_users
        user_id = uuid.uuid1().hex
        payload_data = {'iss': user, 'sub': user_id, 'exp': exp}
        secret = state.settings.get('secret')
        if secret is None:
            return {"errors": ['missing secret']}
        token = jwt.encode(payload=payload_data, key=secret, algorithm="HS256")

        users |= {user_id: user}
        return {'token': token}
    else:
        return {"errors": ['failed pam authentication']}

def get_user_context(request):
    context = {}
    context['request'] = request
    context['user'] = None
    if 'Authorization' in request.headers:
        auth = request.headers['Authorization']
        scheme, token = auth.split()
        if scheme.lower() != 'bearer':
            return context

        try:
            secret = state.settings.get('secret')
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            user_id: str = payload.get('sub')
            if user_id is None:
                return context
        except jwt.exceptions.ExpiredSignatureError:
            context['error'] = 'expired token'
            return context
        except jwt.PyJWTError:
            return context
        try:
            users = state.settings['app'].state.vyos_token_users
        except AttributeError:
            return context

        user = users.get(user_id)
        if user is not None:
            context['user'] = user

    return context
