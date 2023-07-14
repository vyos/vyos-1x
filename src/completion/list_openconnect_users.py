#!/usr/bin/env python3
#
# Copyright (C) 2019-2022 VyOS maintainers and contributors
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

from vyos.config import Config
from vyos.utils.dict import dict_search

def get_user_from_ocserv():
    config = Config()
    base = ['vpn', 'openconnect', 'authentication', 'local-users', 'username']
    openconnect = config.get_config_dict(base, effective=True, key_mangling=('-', '_'))
    users = []
    try:
        for user in (dict_search('username', openconnect) or []):
            users.append(user)
    except:
        pass
    return users

if __name__ == "__main__":
    users = []
    users = get_user_from_ocserv()
    print(" ".join(users))

