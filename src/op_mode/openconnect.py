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

import sys
import json

from tabulate import tabulate
from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import rc_cmd

import vyos.opmode


occtl        = '/usr/bin/occtl'
occtl_socket = '/run/ocserv/occtl.socket'


def _get_raw_data_sessions():
    rc, out = rc_cmd(f'sudo {occtl} --json --socket-file {occtl_socket} show users')
    if rc != 0:
        raise vyos.opmode.DataUnavailable(out)

    sessions = json.loads(out)
    return sessions


def _get_formatted_sessions(data):
    headers = ["Interface", "Username", "IP", "Remote IP", "RX", "TX", "State", "Uptime"]
    ses_list = []
    for ses in data:
        ses_list.append([
            ses.get("Device", '(none)'), ses.get("Username", '(none)'),
            ses.get("IPv4", '(none)'), ses.get("Remote IP", '(none)'),
            ses.get("_RX", '(none)'), ses.get("_TX", '(none)'),
            ses.get("State", '(none)'), ses.get("_Connected at", '(none)')
        ])
    if len(ses_list) > 0:
        output = tabulate(ses_list, headers)
    else:
        output = 'No active openconnect sessions'
    return output


def show_sessions(raw: bool):
    config = ConfigTreeQuery()
    if not config.exists('vpn openconnect'):
        raise vyos.opmode.UnconfiguredSubsystem('Openconnect is not configured')

    openconnect_data = _get_raw_data_sessions()
    if raw:
        return openconnect_data
    return _get_formatted_sessions(openconnect_data)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
