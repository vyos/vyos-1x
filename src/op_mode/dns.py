#!/usr/bin/env python3
#
# Copyright (C) 2022-2024 VyOS maintainers and contributors
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


import typing
import sys
import vyos.opmode

from tabulate import tabulate
from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import cmd, rc_cmd


def _forwarding_data_to_dict(data, sep="\t") -> dict:
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


def _get_forwarding_statistics_raw() -> dict:
    command = cmd('rec_control get-all')
    data = _forwarding_data_to_dict(command)
    data['cache-size'] = "{0:.2f}".format( int(
        cmd('rec_control get cache-bytes')) / 1024 )
    return data


def _get_forwarding_statistics_formatted(data):
    cache_entries = data.get('cache-entries')
    max_cache_entries = data.get('max-cache-entries')
    cache_size = data.get('cache-size')
    data_entries = [[cache_entries, max_cache_entries, f'{cache_size} kbytes']]
    headers = ["Cache entries", "Max cache entries" , "Cache size"]
    output = tabulate(data_entries, headers, numalign="left")
    return output

def _verify_forwarding(func):
    """Decorator checks if DNS Forwarding config exists"""
    from functools import wraps

    @wraps(func)
    def _wrapper(*args, **kwargs):
        config = ConfigTreeQuery()
        if not config.exists('service dns forwarding'):
            raise vyos.opmode.UnconfiguredSubsystem('DNS Forwarding is not configured')
        return func(*args, **kwargs)
    return _wrapper

@_verify_forwarding
def show_forwarding_statistics(raw: bool):
    dns_data = _get_forwarding_statistics_raw()
    if raw:
        return dns_data
    else:
        return _get_forwarding_statistics_formatted(dns_data)

@_verify_forwarding
def reset_forwarding(all: bool, domain: typing.Optional[str]):
    """
    Reset DNS Forwarding cache

    :param all (bool): reset cache all domains
    :param domain (str): reset cache for specified domain
    """
    if all:
        rc, output = rc_cmd('rec_control wipe-cache ".$"')
        if rc != 0:
            print(output)
            return None
        print('DNS Forwarding cache reset for all domains!')
        return output
    elif domain:
        rc, output = rc_cmd(f'rec_control wipe-cache "{domain}$"')
        if rc != 0:
            print(output)
            return None
        print(f'DNS Forwarding cache reset for domain "{domain}"!')
        return output

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
