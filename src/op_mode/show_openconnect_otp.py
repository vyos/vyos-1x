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

import argparse
import os

from vyos.config import Config
from vyos.xml import defaults
from vyos.configdict import dict_merge
from vyos.util import popen
from base64 import b32encode

otp_file = '/run/ocserv/users.oath'

def check_uname_otp(username):
    """
    Check if "username" exists and have an OTP key
    """
    config = Config()
    base_key = ['vpn', 'openconnect', 'authentication', 'local-users', 'username', username, 'otp', 'key']
    if not config.exists(base_key):
        return None
    return True

def get_otp_ocserv(username):
    config = Config()
    base = ['vpn', 'openconnect']
    if not config.exists(base):
        return None
    ocserv = config.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    ocserv = dict_merge(default_values, ocserv)
    # workaround a "know limitation" - https://phabricator.vyos.net/T2665
    del ocserv['authentication']['local_users']['username']['otp']
    if not ocserv["authentication"]["local_users"]["username"]:
        return None
    default_ocserv_usr_values = default_values['authentication']['local_users']['username']['otp']
    for user, params in ocserv['authentication']['local_users']['username'].items():
        # Not every configuration requires OTP settings
        if ocserv['authentication']['local_users']['username'][user].get('otp'):
            ocserv['authentication']['local_users']['username'][user]['otp'] = dict_merge(default_ocserv_usr_values, ocserv['authentication']['local_users']['username'][user]['otp'])
    result = ocserv['authentication']['local_users']['username'][username]
    return result

def display_otp_ocserv(username, params, info):
    hostname = os.uname()[1]
    key_hex = params['otp']['key']
    otp_length = params['otp']['otp_length']
    interval = params['otp']['interval']
    token_type = params['otp']['token_type']
    if token_type == 'hotp-time':
        token_type_acrn = 'totp'
    key_base32 = b32encode(bytes.fromhex(key_hex)).decode()
    otp_url = ''.join(["otpauth://",token_type_acrn,"/",username,"@",hostname,"?secret=",key_base32,"&digits=",otp_length,"&period=",interval])
    qrcode,err = popen('qrencode -t ansiutf8', input=otp_url)

    if info == 'full':
        print("# You can share it with the user, he just needs to scan the QR in his OTP app")
        print("# username: ", username)
        print("# OTP KEY: ", key_base32)
        print("# OTP URL: ", otp_url)
        print(qrcode)
        print('# To add this OTP key to configuration, run the following commands:')
        print(f"set vpn openconnect authentication local-users username {username} otp key '{key_hex}'")
        if interval != "30":
            print(f"set vpn openconnect authentication local-users username {username} otp interval '{interval}'")
        if otp_length != "6":
            print(f"set vpn openconnect authentication local-users username {username} otp otp-length '{otp_length}'")
    elif info == 'key-hex':
        print("# OTP key in hexadecimal: ")
        print(key_hex)
    elif info == 'key-b32':
        print("# OTP key in Base32: ")
        print(key_base32)
    elif info == 'qrcode':
        print(f"# QR code for OpenConnect user '{username}'")
        print(qrcode)
    elif info == 'uri':
        print(f"# URI for OpenConnect user '{username}'")
        print(otp_url)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False, description='Show OTP authentication information for selected user')
    parser.add_argument('--user', action="store", type=str, default='', help='Username')
    parser.add_argument('--info', action="store", type=str, default='full', help='Wich information to display')

    args = parser.parse_args()
    check_otp = check_uname_otp(args.user)
    if check_otp:
        user_otp_params = get_otp_ocserv(args.user)
        display_otp_ocserv(args.user, user_otp_params, args.info)
    else:
        print(f'There is no such user ("{args.user}") with an OTP key configured')
