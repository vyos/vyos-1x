#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

import sys
import os

from vyos.config import Config
from vyos import ConfigError

default_config_data = {
    'deleted': False,
    'radius_server': [],
    'radius_source': '',
    'user': []
}

def get_config():
    login = default_config_data
    conf = Config()
    base_level = ['system', 'login']

    if not conf.exists(base_level):
        login['deleted'] = True
        return login

    if conf.exists(base_level + ['radius', 'source-address']):
        login['radius_source'] = conf.return_value(['radius', 'source-address'])

    # Read in all RADIUS servers and store to list
    for server in conf.list_nodes(base_level + ['radius', 'server']):
        radius = {
            'address': server,
            'key': '',
            'port': '1812',
            'timeout': '2'
        }
        conf.set_level(base_level + ['radius', 'server', server])

        # RADIUS shared secret
        if conf.exists(['key']):
            radius['key'] = conf.return_value(['key'])

        # RADIUS authentication port
        if conf.exists(['port']):
            radius['port'] = conf.return_value(['port'])

        # RADIUS session timeout
        if conf.exists(['timeout']):
            radius['timeout'] = conf.return_value(['timeout'])

        # Append individual RADIUS server configuration to global server list
        login['radius_server'].append(radius)

    # Read in all local users and store to list
    for username in conf.list_nodes(base_level + ['user']):
        user = {
            'name': username,
            'password_plaintext': '',
            'password_encrypted': '',
            'public_keys': [],
            'full_name': '',
            'home_dir': '/home/' + username,
        }
        conf.set_level(base_level + ['user', username])

        # Plaintext password
        if conf.exists(['authentication', 'plaintext-password']):
            user['password_plaintext'] = conf.return_value(['authentication', 'plaintext-password'])

        # Encrypted password
        if conf.exists(['authentication', 'encrypted-password']):
            user['password_encrypted'] = conf.return_value(['authentication', 'encrypted-password'])

        # Read in public keys
        for id in conf.list_nodes(['authentication', 'public-keys']):
            key = {
                'name': id,
                'key': '',
                'options': '',
                'type': ''
            }
            conf.set_level(base_level + ['user', username, 'authentication', 'public-keys', id])

            # Public Key portion
            if conf.exists(['key']):
                user['key'] = conf.return_value(['key'])

            # Options for individual public key
            if conf.exists(['options']):
                user['options'] = conf.return_value(['options'])

            # Type of public key
            if conf.exists(['type']):
                user['type'] = conf.return_value(['type'])

            # Append individual public key to list of user keys
            user['public_keys'].append(key)

        # set proper config level
        conf.set_level(base_level + ['user', username])

        # User real name
        if conf.exists(['full-name']):
            user['full_name'] = conf.return_value(['full-name'])

        # User home-directory
        if conf.exists(['home-directory']):
            user['home_dir'] = conf.return_value(['home-directory'])

    return login

def verify(login):
    pass

def generate(login):
    import pprint
    pprint.pprint(login)

    pass

def apply(login):
    pass

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
