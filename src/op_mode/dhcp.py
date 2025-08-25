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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import typing

from datetime import datetime
from datetime import timezone
from glob import glob
from ipaddress import ip_address
from tabulate import tabulate

import vyos.opmode

from vyos.base import Warning
from vyos.configquery import ConfigTreeQuery

from vyos.kea import kea_get_active_config
from vyos.kea import kea_get_dhcp_pools
from vyos.kea import kea_get_leases
from vyos.kea import kea_get_server_leases
from vyos.kea import kea_get_static_mappings
from vyos.kea import kea_delete_lease
from vyos.utils.process import call
from vyos.utils.process import is_systemd_service_running

time_string = '%a %b %d %H:%M:%S %Z %Y'

config = ConfigTreeQuery()
lease_valid_states = [
    'all',
    'active',
    'free',
    'expired',
    'released',
    'abandoned',
    'reset',
    'backup',
]
sort_valid_inet = [
    'end',
    'mac',
    'hostname',
    'ip',
    'pool',
    'remaining',
    'start',
    'state',
]
sort_valid_inet6 = [
    'end',
    'duid',
    'ip',
    'last_communication',
    'pool',
    'remaining',
    'state',
    'type',
]
mapping_sort_valid = ['mac', 'ip', 'pool', 'duid']

stale_warn_msg = 'DHCP server is configured but not started. Data may be stale.'

ArgFamily = typing.Literal['inet', 'inet6']
ArgState = typing.Literal[
    'all', 'active', 'free', 'expired', 'released', 'abandoned', 'reset', 'backup'
]
ArgOrigin = typing.Literal['local', 'remote']


def _get_raw_server_leases(
    config, family='inet', vrf='', pool=None, sorted=None, state=[], origin=None
) -> list:
    inet_suffix = '6' if family == 'inet6' else '4'
    pools = [pool] if pool else kea_get_dhcp_pools(config, inet_suffix)

    mappings = kea_get_server_leases(config, inet_suffix, vrf, pools, state, origin)

    if sorted:
        if sorted == 'ip':
            mappings.sort(key=lambda x: ip_address(x['ip']))
        else:
            mappings.sort(key=lambda x: x[sorted])
    return mappings


def _get_formatted_server_leases(raw_data, family='inet'):
    data_entries = []
    if family == 'inet':
        for lease in raw_data:
            ipaddr = lease.get('ip')
            hw_addr = lease.get('mac')
            state = lease.get('state')
            start = datetime.fromtimestamp(lease.get('start'), timezone.utc)
            end = (
                datetime.fromtimestamp(lease.get('end'), timezone.utc)
                if lease.get('end')
                else '-'
            )
            remain = lease.get('remaining')
            pool = lease.get('pool')
            hostname = lease.get('hostname')
            origin = lease.get('origin')
            data_entries.append(
                [ipaddr, hw_addr, state, start, end, remain, pool, hostname, origin]
            )

        headers = [
            'IP Address',
            'MAC address',
            'State',
            'Lease start',
            'Lease expiration',
            'Remaining',
            'Pool',
            'Hostname',
            'Origin',
        ]

    if family == 'inet6':
        for lease in raw_data:
            ipaddr = lease.get('ip')
            state = lease.get('state')
            start = datetime.fromtimestamp(
                lease.get('last_communication'), timezone.utc
            )
            end = (
                datetime.fromtimestamp(lease.get('end'), timezone.utc)
                if lease.get('end')
                else '-'
            )
            remain = lease.get('remaining')
            lease_type = lease.get('type')
            pool = lease.get('pool')
            host_identifier = lease.get('duid')
            data_entries.append(
                [ipaddr, state, start, end, remain, lease_type, pool, host_identifier]
            )

        headers = [
            'IPv6 address',
            'State',
            'Last communication',
            'Lease expiration',
            'Remaining',
            'Type',
            'Pool',
            'DUID',
        ]

    output = tabulate(data_entries, headers, numalign='left')
    return output


def _get_pool_size(pool, family='inet', vrf=''):
    v = 'v6' if family == 'inet6' else ''
    # if vrf is set get the correct base for config
    if vrf:
        base = f'vrf name {vrf} service dhcp{v}-server shared-network-name {pool}'
    else:
        base = f'service dhcp{v}-server shared-network-name {pool}'
    size = 0
    subnets = config.list_nodes(f'{base} subnet')
    for subnet in subnets:
        ranges = config.list_nodes(f'{base} subnet {subnet} range')
        for range in ranges:
            if family == 'inet6':
                start = config.value(f'{base} subnet {subnet} range {range} start')
                stop = config.value(f'{base} subnet {subnet} range {range} stop')
            else:
                start = config.value(f'{base} subnet {subnet} range {range} start')
                stop = config.value(f'{base} subnet {subnet} range {range} stop')
            # Add +1 because both range boundaries are inclusive
            size += int(ip_address(stop)) - int(ip_address(start)) + 1
    return size


def _get_raw_server_pool_statistics(config, family='inet', vrf='', pool=None):
    inet_suffix = '6' if family == 'inet6' else '4'
    pools = [pool] if pool else kea_get_dhcp_pools(config, inet_suffix)

    stats = []
    for p in pools:
        size = _get_pool_size(family=family, vrf=vrf, pool=p)
        leases = len(_get_raw_server_leases(config, family=family, vrf=vrf, pool=p))
        use_percentage = round(leases / size * 100) if size != 0 else 0
        pool_stats = {
            'pool': p,
            'size': size,
            'leases': leases,
            'available': (size - leases),
            'use_percentage': use_percentage,
        }
        stats.append(pool_stats)
    return stats


def _get_formatted_server_pool_statistics(pool_data):
    data_entries = []
    for entry in pool_data:
        pool = entry.get('pool')
        size = entry.get('size')
        leases = entry.get('leases')
        available = entry.get('available')
        use_percentage = entry.get('use_percentage')
        use_percentage = f'{use_percentage}%'
        data_entries.append([pool, size, leases, available, use_percentage])

    headers = ['Pool', 'Size', 'Leases', 'Available', 'Usage']
    output = tabulate(data_entries, headers, numalign='left')
    return output


def _get_raw_server_static_mappings(config, family='inet', pool=None, sorted=None):
    inet_suffix = '6' if family == 'inet6' else '4'
    pools = [pool] if pool else kea_get_dhcp_pools(config, inet_suffix)

    mappings = kea_get_static_mappings(config, inet_suffix, pools)

    if sorted:
        if sorted == 'ip':
            mappings.sort(key=lambda x: ip_address(x['ip']))
        else:
            mappings.sort(key=lambda x: x[sorted])
    return mappings


def _get_formatted_server_static_mappings(raw_data):
    data_entries = []

    for entry in raw_data:
        pool = entry.get('pool')
        subnet = entry.get('subnet')
        hostname = entry.get('hostname')
        ip_addr = entry.get('ip', 'N/A')
        mac_addr = entry.get('mac', 'N/A')
        duid = entry.get('duid', 'N/A')
        desc = entry.get('description', 'N/A')
        data_entries.append([pool, subnet, hostname, ip_addr, mac_addr, duid, desc])

    headers = [
        'Pool',
        'Subnet',
        'Hostname',
        'IP Address',
        'MAC Address',
        'DUID',
        'Description',
    ]
    output = tabulate(data_entries, headers, numalign='left')
    return output


def _verify_server(func):
    """Decorator checks if DHCP(v6) config exists"""
    from functools import wraps

    @wraps(func)
    def _wrapper(*args, **kwargs):
        config = ConfigTreeQuery()
        family = kwargs.get('family')
        vrf = kwargs.get('vrf')
        v = 'v6' if family == 'inet6' else ''

        # Check if config does not exist
        if vrf:
            unconf_message = f'DHCP{v} server is not configured for VRF {vrf}'
            if not config.exists(f'vrf name {vrf} service dhcp{v}-server'):
                raise vyos.opmode.UnconfiguredSubsystem(unconf_message)
        else:
            unconf_message = f'DHCP{v} server is not configured'
            if not config.exists(f'service dhcp{v}-server'):
                raise vyos.opmode.UnconfiguredSubsystem(unconf_message)

        # return
        return func(*args, **kwargs)

    return _wrapper


def _verify_client(func):
    """Decorator checks if interface is configured as DHCP client"""
    from functools import wraps
    from vyos.ifconfig import Section

    @wraps(func)
    def _wrapper(*args, **kwargs):
        config = ConfigTreeQuery()
        family = kwargs.get('family')
        v = 'v6' if family == 'inet6' else ''
        interface = kwargs.get('interface')
        interface_path = Section.get_config_path(interface)
        unconf_message = f'DHCP{v} client not configured on interface {interface}!'

        # Check if config does not exist
        if not config.exists(f'interfaces {interface_path} address dhcp{v}'):
            raise vyos.opmode.UnconfiguredObject(unconf_message)
        return func(*args, **kwargs)

    return _wrapper


@_verify_server
def show_server_pool_statistics(
    raw: bool, family: ArgFamily, vrf: str, pool: typing.Optional[str]
):
    v = 'v6' if family == 'inet6' else ''
    inet_suffix = '6' if family == 'inet6' else '4'

    if vrf:
        service = f'kea-dhcp{inet_suffix}-server@{vrf}.service'
    else:
        service = f'kea-dhcp{inet_suffix}-server.service'

    if not is_systemd_service_running(service):
        Warning(stale_warn_msg)

    try:
        active_config = kea_get_active_config(inet_suffix, vrf)
    except Exception:
        if vrf:
            raise vyos.opmode.DataUnavailable(
                f'Cannot fetch DHCP server configuration for VRF {vrf}'
            )
        else:
            raise vyos.opmode.DataUnavailable('Cannot fetch DHCP server configuration')

    active_pools = kea_get_dhcp_pools(active_config, inet_suffix)

    if pool and active_pools and pool not in active_pools:
        if vrf:
            raise vyos.opmode.IncorrectValue(
                f'DHCP{v} pool "{pool}" does not exist for VRF {vrf}!'
            )
        else:
            raise vyos.opmode.IncorrectValue(f'DHCP{v} pool "{pool}" does not exist!')

    pool_data = _get_raw_server_pool_statistics(
        active_config, family=family, vrf=vrf, pool=pool
    )
    if raw:
        return pool_data
    else:
        return _get_formatted_server_pool_statistics(pool_data)


@_verify_server
def show_server_leases(
    raw: bool,
    family: ArgFamily,
    vrf: str,
    pool: typing.Optional[str],
    sorted: typing.Optional[str],
    state: typing.Optional[ArgState],
    origin: typing.Optional[ArgOrigin],
):
    v = 'v6' if family == 'inet6' else ''
    inet_suffix = '6' if family == 'inet6' else '4'

    if vrf:
        service = f'kea-dhcp{inet_suffix}-server@{vrf}.service'
    else:
        service = f'kea-dhcp{inet_suffix}-server.service'

    if not is_systemd_service_running(service):
        Warning(stale_warn_msg)

    try:
        active_config = kea_get_active_config(inet_suffix, vrf)
    except Exception:
        if vrf:
            raise vyos.opmode.DataUnavailable(
                f'Cannot fetch DHCP server configuration for VRF {vrf}'
            )
        else:
            raise vyos.opmode.DataUnavailable('Cannot fetch DHCP server configuration')

    active_pools = kea_get_dhcp_pools(active_config, inet_suffix)

    if pool and active_pools and pool not in active_pools:
        if vrf:
            raise vyos.opmode.IncorrectValue(
                f'DHCP{v} pool "{pool}" does not exist for VRF {vrf}!'
            )
        else:
            raise vyos.opmode.IncorrectValue(f'DHCP{v} pool "{pool}" does not exist!')

    sort_valid = sort_valid_inet6 if family == 'inet6' else sort_valid_inet
    if sorted and sorted not in sort_valid:
        raise vyos.opmode.IncorrectValue(f'DHCP{v} sort "{sorted}" is invalid!')

    if state and state not in lease_valid_states:
        raise vyos.opmode.IncorrectValue(f'DHCP{v} state "{state}" is invalid!')

    lease_data = _get_raw_server_leases(
        config=active_config,
        family=family,
        vrf=vrf,
        pool=pool,
        sorted=sorted,
        state=state,
        origin=origin,
    )
    if raw:
        return lease_data
    else:
        return _get_formatted_server_leases(lease_data, family=family)


@_verify_server
def show_server_static_mappings(
    raw: bool,
    family: ArgFamily,
    vrf: str,
    pool: typing.Optional[str],
    sorted: typing.Optional[str],
):
    v = 'v6' if family == 'inet6' else ''
    inet_suffix = '6' if family == 'inet6' else '4'

    if vrf:
        service = f'kea-dhcp{inet_suffix}-server@{vrf}.service'
    else:
        service = f'kea-dhcp{inet_suffix}-server.service'

    if not is_systemd_service_running(service):
        Warning(stale_warn_msg)

    try:
        active_config = kea_get_active_config(inet_suffix, vrf)
    except Exception:
        if vrf:
            raise vyos.opmode.DataUnavailable(
                f'Cannot fetch DHCP server configuration for VRF {vrf}'
            )
        else:
            raise vyos.opmode.DataUnavailable('Cannot fetch DHCP server configuration')

    active_pools = kea_get_dhcp_pools(active_config, inet_suffix)

    if pool and active_pools and pool not in active_pools:
        if vrf:
            raise vyos.opmode.IncorrectValue(
                f'DHCP{v} pool "{pool}" does not exist for VRF {vrf}!'
            )
        else:
            raise vyos.opmode.IncorrectValue(f'DHCP{v} pool "{pool}" does not exist!')

    if sorted and sorted not in mapping_sort_valid:
        raise vyos.opmode.IncorrectValue(f'DHCP{v} sort "{sorted}" is invalid!')

    static_mappings = _get_raw_server_static_mappings(
        config=active_config, family=family, pool=pool, sorted=sorted
    )
    if raw:
        return static_mappings
    else:
        return _get_formatted_server_static_mappings(static_mappings)


def _lease_valid(inet, vrf, address):
    leases = kea_get_leases(inet, vrf)
    return any(lease['ip-address'] == address for lease in leases)


@_verify_server
def clear_dhcp_server_lease(family: ArgFamily, vrf: str, address: str):
    v = 'v6' if family == 'inet6' else ''
    inet = '6' if family == 'inet6' else '4'

    if not _lease_valid(inet, vrf, address):
        print(f'Lease not found on DHCP{v} server')
        return None

    if not kea_delete_lease(inet, vrf, address):
        print(f'Failed to clear lease for "{address}"')
        return None

    print(f'Lease "{address}" has been cleared')


def _get_raw_client_leases(family='inet', interface=None):
    from time import mktime
    from datetime import datetime
    from vyos.defaults import directories
    from vyos.utils.network import get_interface_vrf

    lease_dir = directories['isc_dhclient_dir']
    lease_files = []
    lease_data = []

    if interface:
        tmp = f'{lease_dir}/dhclient_{interface}.lease'
        if os.path.exists(tmp):
            lease_files.append(tmp)
    else:
        # All DHCP leases
        lease_files = glob(f'{lease_dir}/dhclient_*.lease')

    for lease in lease_files:
        tmp = {}
        with open(lease, 'r') as f:
            for line in f.readlines():
                line = line.rstrip()
                if 'last_update' not in tmp:
                    # ISC dhcp client contains least_update timestamp in human readable
                    # format this makes less sense for an API and also the expiry
                    # timestamp is provided in UNIX time. Convert string (e.g. Sun Jul
                    # 30 18:13:44 CEST 2023) to UNIX time (1690733624)
                    tmp.update(
                        {
                            'last_update': int(
                                mktime(datetime.strptime(line, time_string).timetuple())
                            )
                        }
                    )
                    continue

                k, v = line.split('=')
                tmp.update({k: v.replace("'", '')})

        if 'interface' in tmp:
            vrf = get_interface_vrf(tmp['interface'])
            if vrf:
                tmp.update({'vrf': vrf})

        lease_data.append(tmp)

    return lease_data


def _get_formatted_client_leases(lease_data):
    from time import localtime
    from time import strftime

    from vyos.utils.network import is_intf_addr_assigned

    data_entries = []
    for lease in lease_data:
        if not lease.get('new_ip_address'):
            continue
        data_entries.append(['Interface', lease['interface']])
        if 'new_ip_address' in lease:
            tmp = (
                '[Active]'
                if is_intf_addr_assigned(lease['interface'], lease['new_ip_address'])
                else '[Inactive]'
            )
            data_entries.append(['IP address', lease['new_ip_address'], tmp])
        if 'new_subnet_mask' in lease:
            data_entries.append(['Subnet Mask', lease['new_subnet_mask']])
        if 'new_domain_name' in lease:
            data_entries.append(['Domain Name', lease['new_domain_name']])
        if 'new_routers' in lease:
            data_entries.append(['Router', lease['new_routers']])
        if 'new_domain_name_servers' in lease:
            data_entries.append(['Name Server', lease['new_domain_name_servers']])
        if 'new_dhcp_server_identifier' in lease:
            data_entries.append(['DHCP Server', lease['new_dhcp_server_identifier']])
        if 'new_dhcp_lease_time' in lease:
            data_entries.append(['DHCP Server', lease['new_dhcp_lease_time']])
        if 'vrf' in lease:
            data_entries.append(['VRF', lease['vrf']])
        if 'last_update' in lease:
            tmp = strftime(time_string, localtime(int(lease['last_update'])))
            data_entries.append(['Last Update', tmp])
        if 'new_expiry' in lease:
            tmp = strftime(time_string, localtime(int(lease['new_expiry'])))
            data_entries.append(['Expiry', tmp])

        # Add empty marker
        data_entries.append([''])

    output = tabulate(data_entries, tablefmt='plain')

    return output


def show_client_leases(raw: bool, family: ArgFamily, interface: typing.Optional[str]):
    lease_data = _get_raw_client_leases(family=family, interface=interface)
    if raw:
        return lease_data
    else:
        return _get_formatted_client_leases(lease_data)


@_verify_client
def renew_client_lease(raw: bool, family: ArgFamily, interface: str):
    if not raw:
        v = 'v6' if family == 'inet6' else ''
        print(f'Restarting DHCP{v} client on interface {interface}...')
    if family == 'inet6':
        call(f'systemctl restart dhcp6c@{interface}.service')
    else:
        call(f'systemctl restart dhclient@{interface}.service')


@_verify_client
def release_client_lease(raw: bool, family: ArgFamily, interface: str):
    if not raw:
        v = 'v6' if family == 'inet6' else ''
        print(f'Release DHCP{v} client on interface {interface}...')
    if family == 'inet6':
        call(f'systemctl stop dhcp6c@{interface}.service')
    else:
        call(f'systemctl stop dhclient@{interface}.service')


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
