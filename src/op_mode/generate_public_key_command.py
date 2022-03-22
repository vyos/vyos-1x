#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import urllib.parse

import vyos.remote

def get_key(path):
    url = urllib.parse.urlparse(path)
    if url.scheme == 'file' or url.scheme == '':
        with open(os.path.expanduser(path), 'r') as f:
            key_string = f.read()
    else:
        key_string = vyos.remote.get_remote_config(path)
    return key_string.split()

try:
    username = sys.argv[1]
    algorithm, key, identifier = get_key(sys.argv[2])
except Exception as e:
    print("Failed to retrieve the public key: {}".format(e))
    sys.exit(1)

print('# To add this key as an embedded key, run the following commands:')
print('configure')
print(f'set system login user {username} authentication public-keys {identifier} key {key}')
print(f'set system login user {username} authentication public-keys {identifier} type {algorithm}')
print('commit')
print('save')
print('exit')

