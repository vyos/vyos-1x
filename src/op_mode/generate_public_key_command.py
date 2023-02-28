#!/usr/bin/env python3
#
# Copyright (C) 2022-2023 VyOS maintainers and contributors
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
from vyos.template import generate_uuid4


def get_key(path) -> list:
    """Get public keys from a local file or remote URL

    Args:
        path: Path to the public keys file

    Returns: list of public keys split by new line

    """
    url = urllib.parse.urlparse(path)
    if url.scheme == 'file' or url.scheme == '':
        with open(os.path.expanduser(path), 'r') as f:
            key_string = f.read()
    else:
        key_string = vyos.remote.get_remote_config(path)
    return key_string.split('\n')


if __name__ == "__main__":
    first_loop = True

    for k in get_key(sys.argv[2]):
        k = k.split()
        # Skip empty list entry
        if k == []:
            continue

        try:
            username = sys.argv[1]
            # Github keys don't have identifier for example 'vyos@localhost'
            # 'ssh-rsa AAAA... vyos@localhost'
            # Generate uuid4 identifier
            identifier = f'github@{generate_uuid4("")}' if sys.argv[2].startswith('https://github.com') else k[2]
            algorithm, key = k[0], k[1]
        except Exception as e:
            print("Failed to retrieve the public key: {}".format(e))
            sys.exit(1)

        if first_loop:
            print('# To add this key as an embedded key, run the following commands:')
            print('configure')
        print(f'set system login user {username} authentication public-keys {identifier} key {key}')
        print(f'set system login user {username} authentication public-keys {identifier} type {algorithm}')

        first_loop = False
