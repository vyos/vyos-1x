# Copyright 2021-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.


from ...session import SessionState


def check_auth(key_list, key):
    if not key_list:
        return None
    key_id = None
    for k in key_list:
        if k['key'] == key:
            key_id = k['id']
    return key_id


def auth_required(key):
    state = SessionState()
    api_keys = None
    api_keys = state.keys
    key_id = check_auth(api_keys, key)
    state.id = key_id
    return key_id
