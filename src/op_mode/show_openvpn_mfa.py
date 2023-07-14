#!/usr/bin/env python3
#
# Copyright 2017-2023 VyOS maintainers and contributors <maintainers@vyos.io>
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

import re
import socket
import urllib.parse
import argparse

from vyos.utils.process import popen

otp_file = '/config/auth/openvpn/{interface}-otp-secrets'

def get_mfa_secret(interface, client):
    try:
        with open(otp_file.format(interface=interface), "r") as f:
            users = f.readlines()
            for user in users:
                if re.search('^' + client + ' ', user):
                    return user.split(':')[3]
    except:
        pass

def get_mfa_uri(client, secret):
    hostname = socket.gethostname()
    fqdn = socket.getfqdn()
    uri = 'otpauth://totp/{hostname}:{client}@{fqdn}?secret={secret}'

    return urllib.parse.quote(uri.format(hostname=hostname, client=client, fqdn=fqdn, secret=secret), safe='/:@?=')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False, description='Show two-factor authentication information')
    parser.add_argument('--intf', action="store", type=str, default='', help='only show the specified interface')
    parser.add_argument('--user', action="store", type=str, default='', help='only show the specified users')
    parser.add_argument('--action', action="store", type=str, default='show', help='action to perform')

    args = parser.parse_args()
    secret = get_mfa_secret(args.intf, args.user)

    if args.action == "secret" and secret:
        print(secret)

    if args.action == "uri" and secret:
        uri = get_mfa_uri(args.user, secret)
        print(uri)

    if args.action == "qrcode" and secret:
        uri = get_mfa_uri(args.user, secret)
        qrcode,err = popen('qrencode -t ansiutf8', input=uri)
        print(qrcode)

