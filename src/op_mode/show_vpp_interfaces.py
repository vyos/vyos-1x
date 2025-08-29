#!/usr/bin/env python3
#
# Copyright (C) VyOS Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import argparse
import json
from tabulate import tabulate

from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import rc_cmd

from vyos.vpp import VPPControl
from vyos.vpp.utils import (
    vpp_ifaces_list,
    vpp_ip_addresses_by_index,
    vpp_ifaces_stats,
)


def get_iproute_address_list(interface: str) -> list:
    """Get data from the Linux command 'ip --json address list dev {interface}' and return a list info
    for the given interface.

    Args:
        interface (str): Interface name.

    Returns:
        list: A dictionary containing the JSON data from the 'ip --json address list' command for the specified interface.
    """
    rc, out = rc_cmd(f'ip --json address list dev {interface}')
    if rc:
        return []
    return json.loads(out)


def get_iproute_link_list(interface):
    """Get data from the Linux command 'ip --json link show dev {interface}' and return a list info
    for the given interface.

    Args:
        interface (str): Interface name.

    Returns:
        list: A dictionary containing the JSON data from the 'ip --json link show' command for the specified interface.
    """
    rc, out = rc_cmd(f'ip --json link list dev {interface}')
    if rc:
        return []
    return json.loads(out)


def merge_dicts(*dicts) -> dict:
    """Merge dictionaries into a new dictionary.

    Args:
        *dicts: Any number of dictionaries.

    Returns:
        dict: A new dictionary containing all the key-value pairs from the given dictionaries.
    """
    merged = {}
    for dictionary in dicts:
        merged.update(dictionary)
    return merged


def show_interfaces(interfaces_list: list) -> str:
    """Get JSON info from linux and represent it in a table format
    Use tabulate to generate table

    Interface        IP Address             Mtu           S/L  Description
    ---------        ----------             ---           ---  -----------
    dum0             203.0.113.1/32         1500          u/u
                     100.64.1.1/24
    eth0             192.168.122.14/24      1500          u/u  WAN

    :return:
    """
    table = []
    for interface in interfaces_list:
        # Get the data for the interface
        ip_address_data = get_iproute_address_list(interface)
        link_data = get_iproute_link_list(interface)

        # Skip this interface if data is not available
        if not link_data:
            continue
        interface_data = merge_dicts(ip_address_data[0], link_data[0])

        # Get the interface name
        interface_name = interface_data['ifname']

        # Get the IP addresses and their corresponding prefixes
        ip_info = [
            (address['local'], address.get('prefixlen', ''))
            for address in interface_data['addr_info']
        ]

        # Format the IP addresses with prefixes and line breaks
        ip_addresses = '\n'.join(f'{ip}/{prefix}' for ip, prefix in ip_info)

        # Get the MAC address
        mac = interface_data.get('address', 'n/a')

        # Get the MTU
        mtu = interface_data.get('mtu')

        # Get the state of the interface
        state = interface_data['operstate'].lower()

        # Get the description of the interface
        description = interface_data.get('ifalias', '')

        # Create the list of values for the table
        values = [interface_name, ip_addresses, mac, mtu, state, description]

        # Append the list of values to the table
        table.append(values)

    # Print the table with IP addresses listed on separate lines
    headers = ['Interface', 'IP Address', 'MAC', 'MTU', 'State', 'Description']
    return tabulate(table, headers=headers, tablefmt='simple')


def show_interfaces_dataplane(interfaces_list: list, filter_type: str = 'all') -> str:
    table = []
    interface_dp_filter = ('tun', 'tap')
    lcp_pair_list = vpp.lcp_pairs_list()
    vpp_name_kernel_to_kernel_name = {
        entry['vpp_name_kernel']: entry['kernel_name'] for entry in lcp_pair_list
    }
    for interface in interfaces_list:
        interface_name = interface.get('interface_name')
        if filter_type == 'no_tun_tap' and interface_name.startswith(
            interface_dp_filter
        ):
            continue
        if filter_type == 'only_tun_tap' and not interface_name.startswith(
            interface_dp_filter
        ):
            continue
        kernel_name = vpp_name_kernel_to_kernel_name.get(interface_name, '')

        dp_ip_addresses = vpp_ip_addresses_by_index(
            vpp.api, interface.get('sw_if_index')
        )
        ip_addresses = '\n'.join(dp_ip_addresses)

        mac = str(interface.get('l2_address', 'n/a'))
        mtu = interface.get('mtu', [])[0]
        # state
        flags = interface.get('flags')
        state = 'up' if flags == 3 else 'down'

        iftype = interface.get('interface_dev_type').split()[0]

        values = [kernel_name, interface_name, iftype, ip_addresses, mac, mtu, state]
        table.append(values)
    headers = [
        'Kernel',
        'Dataplane',
        'Type',
        'IP Address',
        'MAC',
        'MTU',
        'State',
    ]
    table = sorted(table)
    return tabulate(table, headers=headers, tablefmt='simple')


def show_interfaces_hardware(intf_name) -> str:
    if not intf_name:
        intf_name = ''

    statistics = vpp_ifaces_stats(intf_name)
    for intf, stats in sorted(statistics.items()):
        print(f'\n---------------------------------\nInterface {intf}:\n')
        table = []
        for k, v in stats.items():
            if isinstance(v, dict):
                for i, j in v.items():
                    table.append([f"{k} {i}", j])
            else:
                table.append([k, v])
        print(tabulate(table, tablefmt="presto"))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Show VPP interfaces')
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Show summary of VPP interfaces (ethernet and kernel tun)',
    )
    parser.add_argument(
        '--dataplane', action='store_true', help='Show VPP ethernet interfaces'
    )
    parser.add_argument(
        '--kernel', action='store_true', help='Show VPP kernel interfaces'
    )
    parser.add_argument(
        '--iproute', action='store_true', help='Show interfaces (iproute2)'
    )
    parser.add_argument(
        '--hardware',
        action='store_true',
        help='Show more detailed statistics for VPP interfaces',
    )
    parser.add_argument('--intf-name', action='store', help='Kernel interface name')

    args = parser.parse_args()

    config = ConfigTreeQuery()

    if not config.exists('vpp settings interface'):
        print('VPP interfaces not configured')
        exit(0)

    vpp = VPPControl()
    dp_ifaces_list = vpp_ifaces_list(vpp.api)

    if args.summary:
        print(show_interfaces_dataplane(dp_ifaces_list, filter_type='all'))

    if args.dataplane:
        print(show_interfaces_dataplane(dp_ifaces_list, filter_type='no_tun_tap'))
        exit(0)

    if args.kernel:
        print(show_interfaces_dataplane(dp_ifaces_list, filter_type='only_tun_tap'))

    if args.iproute:
        vpp_interfaces = []
        vpp_ethernet = config.list_nodes('vpp settings interface')
        vpp_interfaces.extend(vpp_ethernet)
        if config.exists('vpp kernel-interfaces'):
            vpp_kernel_interfaces = config.list_nodes('vpp kernel-interfaces')
            vpp_interfaces.extend(vpp_kernel_interfaces)
        print(show_interfaces(interfaces_list=vpp_interfaces))

    if args.hardware:
        show_interfaces_hardware(intf_name=args.intf_name)
