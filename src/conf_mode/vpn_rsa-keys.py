#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import base64
import os
import struct

from sys import exit

from vyos.config import Config
from vyos.util import call
from vyos import ConfigError
from vyos import airbag
from Crypto.PublicKey.RSA import construct

airbag.enable()

LOCAL_KEY_PATHS = ['/config/auth/', '/config/ipsec.d/rsa-keys/']
LOCAL_OUTPUT = '/etc/ipsec.d/certs/localhost.pub'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['vpn', 'rsa-keys']
    if not conf.exists(base):
        return None

    return conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True, no_tag_node_value_mangle=True)

def verify(conf):
    if not conf:
        return

    if 'local_key' in conf and 'file' in conf['local_key']:
        local_key = conf['local_key']['file']
        if not local_key:
            raise ConfigError(f'Invalid local-key')

        if not get_local_key(local_key):
            raise ConfigError(f'File not found for local-key: {local_key}')

def get_local_key(local_key):
    for path in LOCAL_KEY_PATHS:
        if os.path.exists(path + local_key):
            return path + local_key
    return False

def generate(conf):
    if not conf:
        return

    if 'local_key' in conf and 'file' in conf['local_key']:
        local_key = conf['local_key']['file']
        local_key_path = get_local_key(local_key)
        call(f'sudo /usr/bin/openssl rsa -in {local_key_path} -pubout -out {LOCAL_OUTPUT}')

    if 'rsa_key_name' in conf:
        for key_name, key_conf in conf['rsa_key_name'].items():
            if 'rsa_key' not in key_conf:
                continue

            remote_key = key_conf['rsa_key']

            if remote_key[:2] == "0s": # Vyatta format
                remote_key = migrate_from_vyatta_key(remote_key)
            else:
                remote_key = bytes('-----BEGIN PUBLIC KEY-----\n' + remote_key + '\n-----END PUBLIC KEY-----\n', 'utf-8')

            with open(f'/etc/ipsec.d/certs/{key_name}.pub', 'wb') as f:
                f.write(remote_key)

def migrate_from_vyatta_key(data):
    data = base64.b64decode(data[2:])
    length = struct.unpack('B', data[:1])[0]
    e = int.from_bytes(data[1:1+length], 'big')
    n = int.from_bytes(data[1+length:], 'big')
    pubkey = construct((n, e))
    return pubkey.exportKey(format='PEM')

def apply(conf):
    if not conf:
        return

    call('sudo /usr/sbin/ipsec rereadall')
    call('sudo /usr/sbin/ipsec reload')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
