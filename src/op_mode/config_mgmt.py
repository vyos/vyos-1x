#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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

import sys
import typing

import vyos.opmode
from vyos.config_mgmt import ConfigMgmt

def show_commit_diff(raw: bool, rev: int, revb: typing.Optional[int],
                     commands: bool):
    config_mgmt = ConfigMgmt()
    config_diff = config_mgmt.show_commit_diff(rev, revb, commands)

    if raw:
        revb = (rev+1) if revb is None else revb
        if commands:
            d = {f'config_command_diff_{revb}_{rev}': config_diff}
        else:
            d = {f'config_file_diff_{revb}_{rev}': config_diff}
        return d

    return config_diff

def show_commit_file(raw: bool, rev: int):
    config_mgmt = ConfigMgmt()
    config_file = config_mgmt.show_commit_file(rev)

    if raw:
        d = {f'config_revision_{rev}': config_file}
        return d

    return config_file

def show_commit_log(raw: bool):
    config_mgmt = ConfigMgmt()

    msg = ''
    if config_mgmt.max_revisions == 0:
        msg = ('commit-revisions is not configured;\n'
               'commit log is empty or stale:\n\n')

    data = config_mgmt.get_raw_log_data()
    if raw:
        return data

    out = config_mgmt.format_log_data(data)
    out = msg + out

    return out

def show_commit_log_brief(raw: bool):
    # used internally for completion help for 'rollback'
    # option 'raw' will return same as 'show_commit_log'
    config_mgmt = ConfigMgmt()

    data = config_mgmt.get_raw_log_data()
    if raw:
        return data

    out = config_mgmt.format_log_data_brief(data)

    return out

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
