
from .. import state

def check_auth(key_list, key):
    if not key_list:
        return None
    key_id = None
    for k in key_list:
        if k['key'] == key:
            key_id = k['id']
    return key_id

def auth_required(key):
    api_keys = None
    api_keys = state.settings['app'].state.vyos_keys
    key_id = check_auth(api_keys, key)
    state.settings['app'].state.vyos_id = key_id
    return key_id
