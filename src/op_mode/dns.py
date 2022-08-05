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

from sys import exit
from tabulate import tabulate

from vyos.configquery import ConfigTreeQuery
from vyos.util import cmd

import vyos.opmode


def _data_to_dict(data, sep="\t") -> dict:
    """
    Return dictionary from plain text
    separated by tab

    cache-entries	73
    cache-hits	0
    uptime	2148
    user-msec	172

    {
      'cache-entries': '73',
      'cache-hits': '0',
      'uptime': '2148',
      'user-msec': '172'
    }
    """
    dictionary = {}
    mylist = [line for line in data.split('\n')]

    for line in mylist:
        if sep in line:
            key, value = line.split(sep)
            dictionary[key] = value
    return dictionary


def _get_raw_forwarding_statistics() -> dict:
    command = cmd('sudo /usr/bin/rec_control --socket-dir=/run/powerdns get-all')
    data = _data_to_dict(command)
    data['cache-size'] = "{0:.2f}".format( int(
        cmd('sudo /usr/bin/rec_control --socket-dir=/run/powerdns get cache-bytes')) / 1024 )
    return data


def _get_formatted_forwarding_statistics(data):
    cache_entries = data.get('cache-entries')
    max_cache_entries = data.get('max-cache-entries')
    cache_size = data.get('cache-size')
    data_entries = [[cache_entries, max_cache_entries, f'{cache_size} kbytes']]
    headers = ["Cache entries", "Max cache entries" , "Cache size"]
    output = tabulate(data_entries, headers, numalign="left")
    return output


def show_forwarding_statistics(raw: bool):

    config = ConfigTreeQuery()
    if not config.exists('service dns forwarding'):
        print("DNS forwarding is not configured")
        exit(0)

    dns_data = _get_raw_forwarding_statistics()
    if raw:
        return dns_data
    else:
        return _get_formatted_forwarding_statistics(dns_data)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
