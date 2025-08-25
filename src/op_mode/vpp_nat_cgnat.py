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

import json
import sys
from tabulate import tabulate

import vyos.opmode
from vyos.configquery import ConfigTreeQuery

from vyos.vpp import VPPControl


def _verify(func):
    """Decorator checks if config for VPP NAT CGNAT exists"""
    from functools import wraps

    @wraps(func)
    def _wrapper(*args, **kwargs):
        config = ConfigTreeQuery()
        base = 'vpp nat cgnat'
        if not config.exists(base):
            raise vyos.opmode.UnconfiguredSubsystem(f'{base} is not configured')

        return func(*args, **kwargs)

    return _wrapper


def _get_raw_output(data_dump):
    data = [json.loads(json.dumps(d._asdict(), default=str)) for d in data_dump]
    return data


def _get_formatted_output_interfaces(vpp, interfaces):
    print('CGNAT interfaces:')
    for interface in interfaces:
        name = vpp.get_interface_name(interface['sw_if_index'])
        iface_type = 'in' if interface['is_inside'] else 'out'
        print(f'  {name} {iface_type}')


def _get_formatted_output_mappings(rules_list):
    data_entries = []
    for rule in rules_list:
        in_addr = rule.get('in_addr')
        in_plen = str(rule.get('in_plen'))
        out_addr = rule.get('out_addr')
        out_plen = str(rule.get('out_plen'))
        sharing_ratio = rule.get('sharing_ratio')
        ports_per_host = rule.get('ports_per_host')
        ses_num = rule.get('ses_num')

        values = [
            f'{in_addr}/{in_plen}',
            f'{out_addr}/{out_plen}',
            sharing_ratio,
            ports_per_host,
            ses_num,
        ]
        data_entries.append(values)
    headers = [
        'Inside',
        'Outside',
        'Sharing ratio',
        'Ports per host',
        'Sessions',
    ]
    out = sorted(data_entries, key=lambda x: x[0])
    return tabulate(out, headers=headers, tablefmt='simple')


@_verify
def show_sessions(raw: bool):
    vpp = VPPControl()
    out = vpp.cli_cmd('show det44 sessions').reply
    out = out.replace('NAT44 deterministic', 'CGNAT')
    return out


@_verify
def show_mappings(raw: bool):
    vpp = VPPControl()
    nat_static_dump = vpp.api.det44_map_dump()
    rules_list: list[dict] = _get_raw_output(nat_static_dump)

    if raw:
        return rules_list

    else:
        return _get_formatted_output_mappings(rules_list)


@_verify
def show_interfaces(raw: bool):
    vpp = VPPControl()
    interfaces_dump = vpp.api.det44_interface_dump()
    interfaces: list[dict] = _get_raw_output(interfaces_dump)

    if raw:
        return interfaces

    else:
        return _get_formatted_output_interfaces(vpp, interfaces)


@_verify
def clear_session(address: str, port: str, ext_address: str, ext_port: str):
    vpp = VPPControl()
    vpp.api.det44_close_session_in(
        in_addr=address,
        in_port=int(port),
        ext_addr=ext_address,
        ext_port=int(ext_port),
    )


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
