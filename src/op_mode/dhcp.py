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
from ipaddress import ip_address
import typing

from datetime import datetime
from sys import exit
from tabulate import tabulate
from isc_dhcp_leases import IscDhcpLeases

from vyos.base import Warning
from vyos.configquery import ConfigTreeQuery

from vyos.util import cmd
from vyos.util import dict_search
from vyos.util import is_systemd_service_running

import vyos.opmode


config = ConfigTreeQuery()
pool_key = "shared-networkname"


def _in_pool(lease, pool):
    if pool_key in lease.sets:
        if lease.sets[pool_key] == pool:
            return True
    return False


def _utc_to_local(utc_dt):
    return datetime.fromtimestamp((datetime.fromtimestamp(utc_dt) - datetime(1970, 1, 1)).total_seconds())


def _format_hex_string(in_str):
    out_str = ""
    # if input is divisible by 2, add : every 2 chars
    if len(in_str) > 0 and len(in_str) % 2 == 0:
        out_str = ':'.join(a+b for a,b in zip(in_str[::2], in_str[1::2]))
    else:
        out_str = in_str

    return out_str


def _find_list_of_dict_index(lst, key='ip', value='') -> int:
    """
    Find the index entry of list of dict matching the dict value
    Exampe:
        % lst = [{'ip': '192.0.2.1'}, {'ip': '192.0.2.2'}]
        % _find_list_of_dict_index(lst, key='ip', value='192.0.2.2')
        % 1
    """
    idx = next((index for (index, d) in enumerate(lst) if d[key] == value), None)
    return idx


def _get_raw_server_leases(family, pool=None) -> list:
    """
    Get DHCP server leases
    :return list
    """
    lease_file = '/config/dhcpdv6.leases' if family == 'inet6' else '/config/dhcpd.leases'
    data = []
    leases = IscDhcpLeases(lease_file).get()
    if pool is not None:
        if config.exists(f'service dhcp-server shared-network-name {pool}'):
            leases = list(filter(lambda x: _in_pool(x, pool), leases))
    for lease in leases:
        data_lease = {}
        data_lease['ip'] = lease.ip
        data_lease['state'] = lease.binding_state
        data_lease['pool'] = lease.sets.get('shared-networkname', '')
        data_lease['end'] = lease.end.timestamp()

        if family == 'inet':
            data_lease['hardware'] = lease.ethernet
            data_lease['start'] = lease.start.timestamp()
            data_lease['hostname'] = lease.hostname

        if family == 'inet6':
            data_lease['last_communication'] = lease.last_communication.timestamp()
            data_lease['iaid_duid'] = _format_hex_string(lease.host_identifier_string)
            lease_types_long = {'na': 'non-temporary', 'ta': 'temporary', 'pd': 'prefix delegation'}
            data_lease['type'] = lease_types_long[lease.type]

        data_lease['remaining'] = lease.end - datetime.utcnow()

        if data_lease['remaining'].days >= 0:
            # substraction gives us a timedelta object which can't be formatted with strftime
            # so we use str(), split gets rid of the microseconds
            data_lease['remaining'] = str(data_lease["remaining"]).split('.')[0]
        else:
            data_lease['remaining'] = ''

        # Do not add old leases
        if data_lease['remaining'] != '':
            data.append(data_lease)

        # deduplicate
        checked = []
        for entry in data:
            addr = entry.get('ip')
            if addr not in checked:
                checked.append(addr)
            else:
                idx = _find_list_of_dict_index(data, key='ip', value=addr)
                data.pop(idx)

    return data


def _get_formatted_server_leases(raw_data, family):
    data_entries = []
    if family == 'inet':
        for lease in raw_data:
            ipaddr = lease.get('ip')
            hw_addr = lease.get('hardware')
            state = lease.get('state')
            start = lease.get('start')
            start =  _utc_to_local(start).strftime('%Y/%m/%d %H:%M:%S')
            end = lease.get('end')
            end =  _utc_to_local(end).strftime('%Y/%m/%d %H:%M:%S')
            remain = lease.get('remaining')
            pool = lease.get('pool')
            hostname = lease.get('hostname')
            data_entries.append([ipaddr, hw_addr, state, start, end, remain, pool, hostname])

        headers = ['IP Address', 'Hardware address', 'State', 'Lease start', 'Lease expiration', 'Remaining', 'Pool',
                   'Hostname']

    if family == 'inet6':
        for lease in raw_data:
            ipaddr = lease.get('ip')
            state = lease.get('state')
            start = lease.get('last_communication')
            start =  _utc_to_local(start).strftime('%Y/%m/%d %H:%M:%S')
            end = lease.get('end')
            end =  _utc_to_local(end).strftime('%Y/%m/%d %H:%M:%S')
            remain = lease.get('remaining')
            lease_type = lease.get('type')
            pool = lease.get('pool')
            host_identifier = lease.get('iaid_duid')
            data_entries.append([ipaddr, state, start, end, remain, lease_type, pool, host_identifier])

        headers = ['IPv6 address', 'State', 'Last communication', 'Lease expiration', 'Remaining', 'Type', 'Pool',
                   'IAID_DUID']

    output = tabulate(data_entries, headers, numalign='left')
    return output


def _get_dhcp_pools(family='inet') -> list:
    v = 'v6' if family == 'inet6' else ''
    pools = config.list_nodes(f'service dhcp{v}-server shared-network-name')
    return pools


def _get_pool_size(pool, family='inet'):
    v = 'v6' if family == 'inet6' else ''
    base = f'service dhcp{v}-server shared-network-name {pool}'
    size = 0
    subnets = config.list_nodes(f'{base} subnet')
    for subnet in subnets:
        if family == 'inet6':
            ranges = config.list_nodes(f'{base} subnet {subnet} address-range start')
        else:
            ranges = config.list_nodes(f'{base} subnet {subnet} range')
        for range in ranges:
            if family == 'inet6':
                start = config.list_nodes(f'{base} subnet {subnet} address-range start')[0]
                stop = config.value(f'{base} subnet {subnet} address-range start {start} stop')
            else:
                start = config.value(f'{base} subnet {subnet} range {range} start')
                stop = config.value(f'{base} subnet {subnet} range {range} stop')
            # Add +1 because both range boundaries are inclusive
            size += int(ip_address(stop)) - int(ip_address(start)) + 1
    return size


def _get_raw_pool_statistics(family='inet', pool=None):
    if pool is None:
        pool = _get_dhcp_pools(family=family)
    else:
        pool = [pool]

    v = 'v6' if family == 'inet6' else ''
    stats = []
    for p in pool:
        subnet = config.list_nodes(f'service dhcp{v}-server shared-network-name {p} subnet')
        size = _get_pool_size(family=family, pool=p)
        leases = len(_get_raw_server_leases(family=family, pool=p))
        use_percentage = round(leases / size * 100) if size != 0 else 0
        pool_stats = {'pool': p, 'size': size, 'leases': leases,
                      'available': (size - leases), 'use_percentage': use_percentage, 'subnet': subnet}
        stats.append(pool_stats)
    return stats


def _get_formatted_pool_statistics(pool_data, family='inet'):
    data_entries = []
    for entry in pool_data:
        pool = entry.get('pool')
        size = entry.get('size')
        leases = entry.get('leases')
        available = entry.get('available')
        use_percentage = entry.get('use_percentage')
        use_percentage = f'{use_percentage}%'
        data_entries.append([pool, size, leases, available, use_percentage])

    headers = ['Pool', 'Size','Leases', 'Available', 'Usage']
    output = tabulate(data_entries, headers, numalign='left')
    return output


def _verify(func):
    """Decorator checks if DHCP(v6) config exists"""
    from functools import wraps

    @wraps(func)
    def _wrapper(*args, **kwargs):
        config = ConfigTreeQuery()
        family = kwargs.get('family')
        v = 'v6' if family == 'inet6' else ''
        unconf_message = f'DHCP{v} server is not configured'
        # Check if config does not exist
        if not config.exists(f'service dhcp{v}-server'):
            raise vyos.opmode.UnconfiguredSubsystem(unconf_message)
        return func(*args, **kwargs)
    return _wrapper


@_verify
def show_pool_statistics(raw: bool, family: str, pool: typing.Optional[str]):
    pool_data = _get_raw_pool_statistics(family=family, pool=pool)
    if raw:
        return pool_data
    else:
        return _get_formatted_pool_statistics(pool_data, family=family)


@_verify
def show_server_leases(raw: bool, family: str):
    # if dhcp server is down, inactive leases may still be shown as active, so warn the user.
    if not is_systemd_service_running('isc-dhcp-server.service'):
        Warning('DHCP server is configured but not started. Data may be stale.')

    leases = _get_raw_server_leases(family)
    if raw:
        return leases
    else:
        return _get_formatted_server_leases(leases, family)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
