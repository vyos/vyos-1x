#!/usr/bin/env python3
#
# Copyright (C) 2019-2023 VyOS maintainers and contributors
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
import argparse
import pwd
import struct
import sys
from time import ctime

from tabulate import tabulate
from vyos.config import Config


class UserInfo:
    def __init__(self, uid, name, user_type, is_locked, login_time, tty, host):
        self.uid = uid
        self.name = name
        self.user_type = user_type
        self.is_locked = is_locked
        self.login_time = login_time
        self.tty = tty
        self.host = host


filters = {
    'default': lambda user: not user.is_locked,  # Default is everything but locked accounts
    'vyos': lambda user: user.user_type == 'vyos',
    'other': lambda user: user.user_type != 'vyos',
    'locked': lambda user: user.is_locked,
    'all': lambda user: True
}


def is_locked(user_name: str) -> bool:
    """Check if a given user has password in shadow db"""

    try:
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore",category=DeprecationWarning)
            import spwd
        encrypted_password = spwd.getspnam(user_name)[1]
        return encrypted_password == '*' or encrypted_password.startswith('!')
    except (KeyError, PermissionError):
        print('Cannot access shadow database, ensure this script is run with sufficient permissions')
        sys.exit(1)


def decode_lastlog(lastlog_file, uid: int):
    """Decode last login info of a given user uid from the lastlog file"""

    struct_fmt = '=L32s256s'
    recordsize = struct.calcsize(struct_fmt)
    lastlog_file.seek(recordsize * uid)
    buf = lastlog_file.read(recordsize)
    if len(buf) < recordsize:
        return None
    (time, tty, host) = struct.unpack(struct_fmt, buf)
    time = 'never logged in' if time == 0 else ctime(time)
    tty = tty.strip(b'\x00')
    host = host.strip(b'\x00')
    return time, tty, host


def list_users():
    cfg = Config()
    vyos_users = cfg.list_effective_nodes('system login user')
    users = []
    with open('/var/log/lastlog', 'rb') as lastlog_file:
        for (name, _, uid, _, _, _, _) in pwd.getpwall():
            lastlog_info = decode_lastlog(lastlog_file, uid)
            if lastlog_info is None:
                continue
            user_info = UserInfo(
                uid, name,
                user_type='vyos' if name in vyos_users else 'other',
                is_locked=is_locked(name),
                login_time=lastlog_info[0],
                tty=lastlog_info[1],
                host=lastlog_info[2])
            users.append(user_info)
    return users


def main():
    parser = argparse.ArgumentParser(prog=sys.argv[0], add_help=False)
    parser.add_argument('type', nargs='?', choices=['all', 'vyos', 'other', 'locked'])
    args = parser.parse_args()

    filter_type = args.type if args.type is not None else 'default'
    filter_expr = filters[filter_type]

    headers = ['Username', 'Type', 'Locked', 'Tty', 'From', 'Last login']
    table_data = []
    for user in list_users():
        if filter_expr(user):
            table_data.append([user.name, user.user_type, user.is_locked, user.tty, user.host, user.login_time])
    print(tabulate(table_data, headers, tablefmt='simple'))


if __name__ == '__main__':
    main()
