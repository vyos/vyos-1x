#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

import json
import re
import sys

from datetime import datetime

from vyos.config import Config
from vyos.utils.process import cmd

import vyos.opmode

wlb_status_file = '/run/wlb_status.json'

status_format = '''Interface: {ifname}
Status: {status}
Last Status Change: {last_change}
Last Interface Success: {last_success}
Last Interface Failure: {last_failure}
Interface Failures: {failures}
'''

def _verify(func):
    """Decorator checks if WLB config exists"""
    from functools import wraps

    @wraps(func)
    def _wrapper(*args, **kwargs):
        config = Config()
        if not config.exists(['load-balancing', 'wan']):
            unconf_message = 'WAN load-balancing is not configured'
            raise vyos.opmode.UnconfiguredSubsystem(unconf_message)
        return func(*args, **kwargs)
    return _wrapper

def _get_raw_data():
    with open(wlb_status_file, 'r') as f:
        data = json.loads(f.read())
        if not data:
            return {}
        return data

def _get_formatted_output(raw_data):
    from time import time

    for ifname, if_data in raw_data.items():
        latest_change = if_data['last_success'] if if_data['last_success'] > if_data['last_failure'] else if_data['last_failure']

        change_dt = datetime.fromtimestamp(latest_change) if latest_change > 0 else None
        success_dt = datetime.fromtimestamp(if_data['last_success']) if if_data['last_success'] > 0 else None
        failure_dt = datetime.fromtimestamp(if_data['last_failure']) if if_data['last_failure'] > 0 else None
        now = datetime.fromtimestamp(time())

        fmt_data = {
            'ifname': ifname,
            'status': "active" if if_data['state'] else "failed",
            'last_change': change_dt.strftime("%Y-%m-%d %H:%M:%S") if change_dt else 'N/A',
            'last_success': str(now - success_dt) if success_dt else 'N/A',
            'last_failure': str(now - failure_dt) if failure_dt else 'N/A',
            'failures': if_data['failure_count']
        }
        print(status_format.format(**fmt_data))

@_verify
def show_summary(raw: bool):
    data = _get_raw_data()

    if raw:
        return data
    else:
        return _get_formatted_output(data)

@_verify
def show_connection(raw: bool):
    res = cmd('sudo conntrack -L -n')
    lines = res.split("\n")
    filtered_lines = [line for line in lines if re.search(r' mark=[1-9]', line)]

    if raw:
        return filtered_lines

    for line in lines:
        print(line)

@_verify
def show_status(raw: bool):
    res = cmd('sudo nft list chain ip vyos_wanloadbalance wlb_mangle_prerouting')
    lines = res.split("\n")
    filtered_lines = [line.replace("\t", "") for line in lines[3:-2] if 'meta mark set' not in line]

    if raw:
        return filtered_lines

    for line in filtered_lines:
        print(line)

if __name__ == "__main__":
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
