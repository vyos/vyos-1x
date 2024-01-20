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


import os
import sys
import time
import typing
import vyos.opmode

from tabulate import tabulate
from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import cmd, rc_cmd
from vyos.template import is_ipv4, is_ipv6

_dynamic_cache_file = r'/run/ddclient/ddclient.cache'

_dynamic_status_columns = {
    'host':        'Hostname',
    'ipv4':        'IPv4 address',
    'status-ipv4': 'IPv4 status',
    'ipv6':        'IPv6 address',
    'status-ipv6': 'IPv6 status',
    'mtime':       'Last update',
}

_forwarding_statistics_columns = {
    'cache-entries':     'Cache entries',
    'max-cache-entries': 'Max cache entries',
    'cache-size':        'Cache size',
}

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

def _get_dynamic_host_records_raw() -> dict:

    data = []

    if os.path.isfile(_dynamic_cache_file): # A ddclient status file might not always exist
        with open(_dynamic_cache_file, 'r') as f:
            for line in f:
                if line.startswith('#'):
                    continue

                props = {}
                # ddclient cache rows have properties in 'key=value' format separated by comma
                # we pick up the ones we are interested in
                for kvraw in line.split(' ')[0].split(','):
                    k, v = kvraw.split('=')
                    if k in list(_dynamic_status_columns.keys()) + ['ip', 'status']:  # ip and status are legacy keys
                        props[k] = v

                # Extract IPv4 and IPv6 address and status from legacy keys
                # Dual-stack isn't supported in legacy format, 'ip' and 'status' are for one of IPv4 or IPv6
                if 'ip' in props:
                    if is_ipv4(props['ip']):
                        props['ipv4'] = props['ip']
                        props['status-ipv4'] = props['status']
                    elif is_ipv6(props['ip']):
                        props['ipv6'] = props['ip']
                        props['status-ipv6'] = props['status']
                    del props['ip']

                # Convert mtime to human readable format
                if 'mtime' in props:
                    props['mtime'] = time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(int(props['mtime'], base=10)))

                data.append(props)

    return data

def _get_dynamic_host_records_formatted(data):
    data_entries = []
    for entry in data:
        data_entries.append([entry.get(key) for key in _dynamic_status_columns.keys()])
    header = _dynamic_status_columns.values()
    output = tabulate(data_entries, header, numalign='left')
    return output

def _get_forwarding_statistics_raw() -> dict:
    command = cmd('rec_control get-all')
    data = _forwarding_data_to_dict(command)
    data['cache-size'] = "{0:.2f} kbytes".format( int(
        cmd('rec_control get cache-bytes')) / 1024 )
    return data

def _get_forwarding_statistics_formatted(data):
    data_entries = []
    data_entries.append([data.get(key) for key in _forwarding_statistics_columns.keys()])
    header = _forwarding_statistics_columns.values()
    output = tabulate(data_entries, header, numalign='left')
    return output

def _verify(target):
    """Decorator checks if config for DNS related service exists"""
    from functools import wraps

    if target not in ['dynamic', 'forwarding']:
        raise ValueError('Invalid target')

    def _verify_target(func):
        @wraps(func)
        def _wrapper(*args, **kwargs):
            config = ConfigTreeQuery()
            if not config.exists(f'service dns {target}'):
                _prefix = f'Dynamic DNS' if target == 'dynamic' else 'DNS Forwarding'
                raise vyos.opmode.UnconfiguredSubsystem(f'{_prefix} is not configured')
            return func(*args, **kwargs)
        return _wrapper
    return _verify_target

@_verify('dynamic')
def show_dynamic_status(raw: bool):
    host_data = _get_dynamic_host_records_raw()
    if raw:
        return host_data
    else:
        return _get_dynamic_host_records_formatted(host_data)

@_verify('dynamic')
def reset_dynamic():
    """
    Reset Dynamic DNS cache
    """
    if os.path.exists(_dynamic_cache_file):
        os.remove(_dynamic_cache_file)
    rc, output = rc_cmd('systemctl restart ddclient.service')
    if rc != 0:
        print(output)
        return None
    print(f'Dynamic DNS state reset!')

@_verify('forwarding')
def show_forwarding_statistics(raw: bool):
    dns_data = _get_forwarding_statistics_raw()
    if raw:
        return dns_data
    else:
        return _get_forwarding_statistics_formatted(dns_data)

@_verify('forwarding')
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
