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
import typing

from datetime import datetime
from glob import glob
from ipaddress import ip_address
from tabulate import tabulate

import vyos.opmode

from vyos.base import Warning
from vyos.configquery import ConfigTreeQuery

from vyos.kea import kea_get_active_config
from vyos.kea import kea_get_leases
from vyos.kea import kea_get_pool_from_subnet_id
from vyos.kea import kea_delete_lease
from vyos.utils.process import is_systemd_service_running
from vyos.utils.process import call

time_string = "%a %b %d %H:%M:%S %Z %Y"

config = ConfigTreeQuery()
lease_valid_states = ['all', 'active', 'free', 'expired', 'released', 'abandoned', 'reset', 'backup']
sort_valid_inet = ['end', 'mac', 'hostname', 'ip', 'pool', 'remaining', 'start', 'state']
sort_valid_inet6 = ['end', 'duid', 'ip', 'last_communication', 'pool', 'remaining', 'state', 'type']
mapping_sort_valid = ['mac', 'ip', 'pool', 'duid']

ArgFamily = typing.Literal['inet', 'inet6']
ArgState = typing.Literal['all', 'active', 'free', 'expired', 'released', 'abandoned', 'reset', 'backup']
ArgOrigin = typing.Literal['local', 'remote']

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


def _get_raw_server_leases(family='inet', pool=None, sorted=None, state=[], origin=None) -> list:
    """
    Get DHCP server leases
    :return list
    """
    inet_suffix = '6' if family == 'inet6' else '4'
    try:
        leases = kea_get_leases(inet_suffix)
    except:
        raise vyos.opmode.DataUnavailable('Cannot fetch DHCP server lease information')

    if pool is None:
        pool = _get_dhcp_pools(family=family)
    else:
        pool = [pool]

    try:
        active_config = kea_get_active_config(inet_suffix)
    except:
        raise vyos.opmode.DataUnavailable('Cannot fetch DHCP server configuration')

    data = []
    for lease in leases:
        lifetime = lease['valid-lft']
        expiry = (lease['cltt'] + lifetime)

        lease['start_timestamp'] = datetime.utcfromtimestamp(expiry - lifetime)
        lease['expire_timestamp'] = datetime.utcfromtimestamp(expiry) if expiry else None

        data_lease = {}
        data_lease['ip'] = lease['ip-address']
        lease_state_long = {0: 'active', 1: 'rejected', 2: 'expired'}
        data_lease['state'] = lease_state_long[lease['state']]
        data_lease['pool'] = kea_get_pool_from_subnet_id(active_config, inet_suffix, lease['subnet-id']) if active_config else '-'
        data_lease['end'] = lease['expire_timestamp'].timestamp() if lease['expire_timestamp'] else None
        data_lease['origin'] = 'local' # TODO: Determine remote in HA

        if family == 'inet':
            data_lease['mac'] = lease['hw-address']
            data_lease['start'] = lease['start_timestamp'].timestamp()
            data_lease['hostname'] = lease['hostname']

        if family == 'inet6':
            data_lease['last_communication'] = lease['start_timestamp'].timestamp()
            data_lease['duid'] = _format_hex_string(lease['duid'])
            data_lease['type'] = lease['type']

            if lease['type'] == 'IA_PD':
                prefix_len = lease['prefix-len']
                data_lease['ip'] += f'/{prefix_len}'

        data_lease['remaining'] = '-'

        if lease['valid-lft'] > 0:
            data_lease['remaining'] = lease['expire_timestamp'] - datetime.utcnow()

            if data_lease['remaining'].days >= 0:
                # substraction gives us a timedelta object which can't be formatted with strftime
                # so we use str(), split gets rid of the microseconds
                data_lease['remaining'] = str(data_lease["remaining"]).split('.')[0]

        # Do not add old leases
        if data_lease['remaining'] != '' and data_lease['pool'] in pool and data_lease['state'] != 'free':
            if not state or state == 'all' or data_lease['state'] in state:
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

    if sorted:
        if sorted == 'ip':
            data.sort(key = lambda x:ip_address(x['ip']))
        else:
            data.sort(key = lambda x:x[sorted])
    return data


def _get_formatted_server_leases(raw_data, family='inet'):
    data_entries = []
    if family == 'inet':
        for lease in raw_data:
            ipaddr = lease.get('ip')
            hw_addr = lease.get('mac')
            state = lease.get('state')
            start = lease.get('start')
            start =  _utc_to_local(start).strftime('%Y/%m/%d %H:%M:%S')
            end = lease.get('end')
            end =  _utc_to_local(end).strftime('%Y/%m/%d %H:%M:%S') if end else '-'
            remain = lease.get('remaining')
            pool = lease.get('pool')
            hostname = lease.get('hostname')
            origin = lease.get('origin')
            data_entries.append([ipaddr, hw_addr, state, start, end, remain, pool, hostname, origin])

        headers = ['IP Address', 'MAC address', 'State', 'Lease start', 'Lease expiration', 'Remaining', 'Pool',
                   'Hostname', 'Origin']

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
            host_identifier = lease.get('duid')
            data_entries.append([ipaddr, state, start, end, remain, lease_type, pool, host_identifier])

        headers = ['IPv6 address', 'State', 'Last communication', 'Lease expiration', 'Remaining', 'Type', 'Pool',
                   'DUID']

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

def _get_raw_server_static_mappings(family='inet', pool=None, sorted=None):
    if pool is None:
        pool = _get_dhcp_pools(family=family)
    else:
        pool = [pool]

    v = 'v6' if family == 'inet6' else ''
    mappings = []
    for p in pool:
        pool_config = config.get_config_dict(['service', f'dhcp{v}-server', 'shared-network-name', p],
                                             get_first_key=True)
        if 'subnet' in pool_config:
            for subnet, subnet_config in pool_config['subnet'].items():
                if 'static-mapping' in subnet_config:
                    for name, mapping_config in subnet_config['static-mapping'].items():
                        mapping = {'pool': p, 'subnet': subnet, 'name': name}
                        mapping.update(mapping_config)
                        mappings.append(mapping)

    if sorted:
        if sorted == 'ip':
            data.sort(key = lambda x:ip_address(x['ip-address']))
        else:
            data.sort(key = lambda x:x[sorted])
    return mappings

def _get_formatted_server_static_mappings(raw_data, family='inet'):
    data_entries = []
    for entry in raw_data:
        pool = entry.get('pool')
        subnet = entry.get('subnet')
        name = entry.get('name')
        ip_addr = entry.get('ip-address', 'N/A')
        mac_addr = entry.get('mac', 'N/A')
        duid = entry.get('duid', 'N/A')
        description = entry.get('description', 'N/A')
        data_entries.append([pool, subnet, name, ip_addr, mac_addr, duid, description])

    headers = ['Pool', 'Subnet', 'Name', 'IP Address', 'MAC Address', 'DUID', 'Description']
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
            raise vyos.opmode.UnconfiguredSubsystem(unconf_message)
        return func(*args, **kwargs)
    return _wrapper

@_verify
def show_pool_statistics(raw: bool, family: ArgFamily, pool: typing.Optional[str]):
    pool_data = _get_raw_pool_statistics(family=family, pool=pool)
    if raw:
        return pool_data
    else:
        return _get_formatted_pool_statistics(pool_data, family=family)


@_verify
def show_server_leases(raw: bool, family: ArgFamily, pool: typing.Optional[str],
                       sorted: typing.Optional[str], state: typing.Optional[ArgState],
                       origin: typing.Optional[ArgOrigin] ):
    # if dhcp server is down, inactive leases may still be shown as active, so warn the user.
    v = '6' if family == 'inet6' else '4'
    if not is_systemd_service_running(f'kea-dhcp{v}-server.service'):
        Warning('DHCP server is configured but not started. Data may be stale.')

    v = 'v6' if family == 'inet6' else ''
    if pool and pool not in _get_dhcp_pools(family=family):
        raise vyos.opmode.IncorrectValue(f'DHCP{v} pool "{pool}" does not exist!')

    if state and state not in lease_valid_states:
        raise vyos.opmode.IncorrectValue(f'DHCP{v} state "{state}" is invalid!')

    sort_valid = sort_valid_inet6 if family == 'inet6' else sort_valid_inet
    if sorted and sorted not in sort_valid:
        raise vyos.opmode.IncorrectValue(f'DHCP{v} sort "{sorted}" is invalid!')

    lease_data = _get_raw_server_leases(family=family, pool=pool, sorted=sorted, state=state, origin=origin)
    if raw:
        return lease_data
    else:
        return _get_formatted_server_leases(lease_data, family=family)

@_verify
def show_server_static_mappings(raw: bool, family: ArgFamily, pool: typing.Optional[str],
                                sorted: typing.Optional[str]):
    v = 'v6' if family == 'inet6' else ''
    if pool and pool not in _get_dhcp_pools(family=family):
        raise vyos.opmode.IncorrectValue(f'DHCP{v} pool "{pool}" does not exist!')

    if sorted and sorted not in mapping_sort_valid:
        raise vyos.opmode.IncorrectValue(f'DHCP{v} sort "{sorted}" is invalid!')

    static_mappings = _get_raw_server_static_mappings(family=family, pool=pool, sorted=sorted)
    if raw:
        return static_mappings
    else:
        return _get_formatted_server_static_mappings(static_mappings, family=family)

def _lease_valid(inet, address):
    leases = kea_get_leases(inet)
    for lease in leases:
        if address == lease['ip-address']:
            return True
    return False

@_verify
def clear_dhcp_server_lease(family: ArgFamily, address: str):
    v = 'v6' if family == 'inet6' else ''
    inet = '6' if family == 'inet6' else '4'

    if not _lease_valid(inet, address):
        print(f'Lease not found on DHCP{v} server')
        return None

    if not kea_delete_lease(inet, address):
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
                    tmp.update({'last_update' : int(mktime(datetime.strptime(line, time_string).timetuple()))})
                    continue

                k, v = line.split('=')
                tmp.update({k : v.replace("'", "")})

        if 'interface' in tmp:
            vrf = get_interface_vrf(tmp['interface'])
            if vrf: tmp.update({'vrf' : vrf})

        lease_data.append(tmp)

    return lease_data

def _get_formatted_client_leases(lease_data, family):
    from time import localtime
    from time import strftime

    from vyos.utils.network import is_intf_addr_assigned

    data_entries = []
    for lease in lease_data:
        if not lease.get('new_ip_address'):
            continue
        data_entries.append(["Interface", lease['interface']])
        if 'new_ip_address' in lease:
            tmp = '[Active]' if is_intf_addr_assigned(lease['interface'], lease['new_ip_address']) else '[Inactive]'
            data_entries.append(["IP address", lease['new_ip_address'], tmp])
        if 'new_subnet_mask' in lease:
            data_entries.append(["Subnet Mask", lease['new_subnet_mask']])
        if 'new_domain_name' in lease:
            data_entries.append(["Domain Name", lease['new_domain_name']])
        if 'new_routers' in lease:
            data_entries.append(["Router", lease['new_routers']])
        if 'new_domain_name_servers' in lease:
            data_entries.append(["Name Server", lease['new_domain_name_servers']])
        if 'new_dhcp_server_identifier' in lease:
            data_entries.append(["DHCP Server", lease['new_dhcp_server_identifier']])
        if 'new_dhcp_lease_time' in lease:
            data_entries.append(["DHCP Server", lease['new_dhcp_lease_time']])
        if 'vrf' in lease:
            data_entries.append(["VRF", lease['vrf']])
        if 'last_update' in lease:
            tmp = strftime(time_string, localtime(int(lease['last_update'])))
            data_entries.append(["Last Update", tmp])
        if 'new_expiry' in lease:
            tmp = strftime(time_string, localtime(int(lease['new_expiry'])))
            data_entries.append(["Expiry", tmp])

        # Add empty marker
        data_entries.append([''])

    output = tabulate(data_entries, tablefmt='plain')

    return output

def show_client_leases(raw: bool, family: ArgFamily, interface: typing.Optional[str]):
    lease_data = _get_raw_client_leases(family=family, interface=interface)
    if raw:
        return lease_data
    else:
        return _get_formatted_client_leases(lease_data, family=family)

@_verify_client
def renew_client_lease(raw: bool, family: ArgFamily, interface: str):
    if not raw:
        v = 'v6' if family == 'inet6' else ''
        print(f'Restarting DHCP{v} client on interface {interface}...')
    if family == 'inet6':
        call(f'systemctl restart dhcp6c@{interface}.service')
    else:
        call(f'systemctl restart dhclient@{interface}.service')

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
