#!/usr/bin/env python3

# Copyright 2017, 2022 VyOS maintainers and contributors <maintainers@vyos.io>
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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.


import sys
import os
import vyos.opmode
from jinja2 import Template
from vyos.config import Config
from vyos.utils.process import popen


users_otp_template = Template("""
{% if info == "full" %}
# You can share it with the user, he just needs to scan the QR in his OTP app
# username: {{username}}
# OTP KEY: {{key_base32}}
# OTP URL: {{otp_url}}
{{qrcode}}
# To add this OTP key to configuration, run the following commands:
set system login user {{username}} authentication otp key '{{key_base32}}'
{% if rate_limit != "3" %}
set system login user {{username}} authentication otp rate-limit '{{rate_limit}}'
{% endif %}
{% if rate_time != "30" %}
set system login user {{username}} authentication otp rate-time '{{rate_time}}'
{% endif %}
{% if window_size != "3" %}
set system login user {{username}} authentication otp window-size '{{window_size}}'
{% endif %}
{% elif info == "key-b32" %}
# OTP key in Base32 for system user {{username}}:
{{key_base32}}
{% elif info == "qrcode" %}
# QR code for system user '{{username}}'
{{qrcode}}
{% elif info == "uri" %}
# URI for system user '{{username}}'
{{otp_url}}
{% endif %}
""", trim_blocks=True, lstrip_blocks=True)


def _check_uname_otp(username:str):
    """
    Check if "username" exists and have an OTP key
    """
    config = Config()
    base_key = ['system', 'login', 'user', username, 'authentication', 'otp', 'key']
    if not config.exists(base_key):
        return None
    return True

def _get_login_otp(username: str, info:str):
    """
    Retrieve user settings from configuration and set some defaults
    """
    config = Config()
    base = ['system', 'login', 'user', username]
    if not config.exists(base):
        return None
    user_otp = config.get_config_dict(base, key_mangling=('-', '_'),
                                      get_first_key=True,
                                      with_recursive_defaults=True)
    result = user_otp['authentication']['otp']
    # Filling in the system and default options
    result['info'] = info
    result['hostname'] = os.uname()[1]
    result['username'] = username
    result['key_base32'] = result['key']
    result['otp_length'] = '6'
    result['interval'] = '30'
    result['token_type'] = 'hotp-time'
    if result['token_type'] == 'hotp-time':
        token_type_acrn = 'totp'
    result['otp_url'] = ''.join(["otpauth://",token_type_acrn,"/",username,"@",\
        result['hostname'],"?secret=",result['key_base32'],"&digits=",\
        result['otp_length'],"&period=",result['interval']])
    result['qrcode'],_ = popen('qrencode -t ansiutf8', input=result['otp_url'])
    return result

def show_login(raw: bool, username: str, info:str):
    '''
    Display OTP parameters for <username>
    '''
    check_otp = _check_uname_otp(username)
    if check_otp:
        user_otp_params = _get_login_otp(username, info)
    else:
        print(f'There is no such user ("{username}") with an OTP key configured')
        print('You can use the following command to generate a key for a user:\n')
        print(f'generate system login username {username} otp-key hotp-time')
        sys.exit(0)
    if raw:
        return user_otp_params
    return users_otp_template.render(user_otp_params)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
