#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
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
import argparse
import sys
import time
from tabulate import tabulate

from vyos.config import Config
from vyos.util import call

cache_file = r'/run/ddclient/ddclient.cache'

columns = {
    'host':        'Hostname',
    'ipv4':        'IPv4 address',
    'status-ipv4': 'IPv4 status',
    'ipv6':        'IPv6 address',
    'status-ipv6': 'IPv6 status',
    'mtime':       'Last update',
}


def _get_formatted_host_records(host_data):
    data_entries = []
    for entry in host_data:
        data_entries.append([entry.get(key) for key in columns.keys()])

    header = columns.values()
    output = tabulate(data_entries, header, numalign='left')
    return output


def show_status():
    # A ddclient status file must not always exist
    if not os.path.exists(cache_file):
        sys.exit(0)

    data = []

    with open(cache_file, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue

            props = {}
            # ddclient cache rows have properties in 'key=value' format separated by comma
            # we pick up the ones we are interested in
            for kvraw in line.split(' ')[0].split(','):
                k, v = kvraw.split('=')
                if k in columns.keys():
                    props[k] = v

            # Convert mtime to human readable format
            if 'mtime' in props:
                props['mtime'] = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(int(props['mtime'], base=10)))

            data.append(props)

    print(_get_formatted_host_records(data))


def update_ddns():
    call('systemctl stop ddclient.service')
    if os.path.exists(cache_file):
        os.remove(cache_file)
    call('systemctl start ddclient.service')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", help="Show DDNS status", action="store_true")
    group.add_argument("--update", help="Update DDNS on a given interface", action="store_true")
    args = parser.parse_args()

    # Do nothing if service is not configured
    c = Config()
    if not c.exists_effective('service dns dynamic'):
        print("Dynamic DNS not configured")
        sys.exit(1)

    if args.status:
        show_status()
    elif args.update:
        update_ddns()
