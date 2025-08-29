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
import typing
from tabulate import tabulate

import vyos.opmode
from vyos.config import Config
from vyos.configquery import ConfigTreeQuery

from vyos.vpp import VPPControl


NO_ACL_INDEX = 0xFFFFFFFF

# ACL action flags
action_map = {
    0: 'deny',
    1: 'permit',
    2: 'permit-reflect',
}

# TCP flag names to bit values
TCP_FLAGS = {
    'FIN': 0x01,
    'SYN': 0x02,
    'RST': 0x04,
    'PSH': 0x08,
    'ACK': 0x10,
    'URG': 0x20,
    'ECN': 0x40,
    'CWR': 0x80,
}


def _verify(target):
    """Decorator checks if config for VPP NAT CGNAT exists"""
    from functools import wraps

    if target not in ['ip', 'macip', 'no_target']:
        raise ValueError('Invalid target')

    def _verify_target(func):
        @wraps(func)
        def _wrapper(*args, **kwargs):
            config = ConfigTreeQuery()
            path = 'vpp acl'
            if target == 'ip':
                path += ' ip'
            elif target == 'macip':
                path += ' macip'
            if not config.exists(path):
                raise vyos.opmode.UnconfiguredSubsystem(f'"{path}" is not configured')
            return func(*args, **kwargs)

        return _wrapper

    return _verify_target


def _get_acl_tag_by_index(vpp, acl_index):
    acl = vpp.api.acl_dump(acl_index=acl_index)
    if acl:
        return acl[0].tag

    return None


def _get_macip_acl_tag_by_index(vpp, acl_index):
    acl = vpp.api.macip_acl_dump(acl_index=acl_index)
    if acl:
        return acl[0].tag

    return None


def _get_tcp_flag_states(value, mask):
    set_flags = []
    unset_flags = []
    for flag, bit in TCP_FLAGS.items():
        if mask & bit:  # This flag is being checked
            if value & bit:
                set_flags.append(flag)
            else:
                unset_flags.append(flag)
    return sorted(set_flags), sorted(unset_flags)


def _get_raw_output_acls(data_dump):
    out = []
    for data in data_dump:
        rules = [json.loads(json.dumps(d._asdict(), default=str)) for d in data.r]
        out.append(
            {
                'acl_index': data.acl_index,
                'tag': data.tag,
                'count': data.count,
                'r': rules,
            }
        )
    return out


def _get_raw_output_interfaces(data_dump):
    ifaces_list = []
    for iface in data_dump:
        if iface.count != 0:
            ifaces_list.append(json.loads(json.dumps(iface._asdict(), default=str)))
    return ifaces_list


def _get_formatted_output_interfaces(vpp, interfaces):
    data_entries = []
    for interface in interfaces:
        name = vpp.get_interface_name(interface.get('sw_if_index'))
        input_acls = []
        for acl_index in interface.get('acls')[: interface.get('n_input')]:
            input_acls.append(_get_acl_tag_by_index(vpp, int(acl_index)))
        output_acls = []
        for acl_index in interface.get('acls')[interface.get('n_input') :]:
            output_acls.append(_get_acl_tag_by_index(vpp, int(acl_index)))
        values = [
            name,
            '\n'.join(input_acls),
            '\n'.join(output_acls),
        ]
        data_entries.append(values)

    headers = ['Interface', 'Input ACLs', 'Output ACLs']
    return tabulate(data_entries, headers=headers, tablefmt='simple')


def _get_formatted_output_macip_interfaces(vpp, interfaces):
    data_entries = []
    for interface in interfaces:
        name = vpp.get_interface_name(interface.get('sw_if_index'))
        acl = _get_macip_acl_tag_by_index(vpp, int(interface.get('acls')[0]))
        data_entries.append([name, acl])

    headers = ['Interface', 'ACL']
    return tabulate(data_entries, headers=headers, tablefmt='simple')


def _get_formatted_output_acls(acls_list):
    conf = Config()

    for acl in acls_list:
        acl_index = acl.get('acl_index')
        tag = acl.get('tag')
        rules = acl.get('r')
        print(
            '\n---------------------------------\n'
            f'IP ACL "tag-name {tag}" acl_index {acl_index}\n'
        )

        path = ['vpp', 'acl', 'ip', 'tag-name', tag, 'rule']
        conf_rules = conf.list_nodes(path)
        data_entries = []
        for rule_index, rule in enumerate(rules):
            srcport_first = str(rule.get('srcport_or_icmptype_first'))
            srcport_last = str(rule.get('srcport_or_icmptype_last'))
            dstport_first = str(rule.get('dstport_or_icmpcode_first'))
            dstport_last = str(rule.get('dstport_or_icmpcode_last'))
            set_flags, unset_flags = _get_tcp_flag_states(
                rule.get('tcp_flags_value'), rule.get('tcp_flags_mask')
            )

            values = [
                conf_rules[rule_index],
                action_map.get(rule.get('is_permit')),
                rule.get('src_prefix'),
                (
                    f'{srcport_first}-{srcport_last}'
                    if srcport_first != srcport_last
                    else srcport_first
                ),
                rule.get('dst_prefix'),
                (
                    f'{dstport_first}-{dstport_last}'
                    if dstport_first != dstport_last
                    else dstport_first
                ),
                rule.get('proto'),
                '\n'.join(set_flags),
                '\n'.join(unset_flags),
            ]
            data_entries.append(values)

        headers = [
            'Rule',
            'Action',
            'Src prefix',
            'Src port',
            'Dst prefix',
            'Dst port',
            'Proto',
            'TCP flags set',
            'TCP flags not set',
        ]
        print(tabulate(data_entries, headers=headers, tablefmt='simple'))
        print('\n')


def _get_formatted_output_macip_acls(acls_list):
    conf = Config()

    for acl in acls_list:
        acl_index = acl.get('acl_index')
        tag = acl.get('tag')
        rules = acl.get('r')
        print(
            '\n---------------------------------\n'
            f'MACIP ACL "tag-name {tag}" acl_index {acl_index}\n'
        )

        path = ['vpp', 'acl', 'macip', 'tag-name', tag, 'rule']
        conf_rules = conf.list_nodes(path)
        data_entries = []
        for rule_index, rule in enumerate(rules):
            values = [
                conf_rules[rule_index],
                action_map.get(rule.get('is_permit')),
                rule.get('src_prefix'),
                rule.get('src_mac'),
                rule.get('src_mac_mask'),
            ]
            data_entries.append(values)

        headers = [
            'Rule',
            'Action',
            'IP prefix',
            'MAC address',
            'MAC mask',
        ]
        print(tabulate(data_entries, headers=headers, tablefmt='simple'))
        print('\n')


def _find_acl_by_tag(acls, tag_name):
    return [acl for acl in acls if acl['tag'] == tag_name]


@_verify('ip')
def show_ip_acls(raw: bool, tag_name: typing.Optional[str]):
    vpp = VPPControl()
    acls_dump = vpp.api.acl_dump(acl_index=NO_ACL_INDEX)
    acls: list[dict] = _get_raw_output_acls(acls_dump)

    if tag_name:
        acls = _find_acl_by_tag(acls, tag_name)

    if raw:
        return acls

    else:
        return _get_formatted_output_acls(acls)


@_verify('macip')
def show_macip_acls(raw: bool, tag_name: typing.Optional[str]):
    vpp = VPPControl()
    acls_dump = vpp.api.macip_acl_dump(acl_index=NO_ACL_INDEX)
    acls: list[dict] = _get_raw_output_acls(acls_dump)

    if tag_name:
        acls = _find_acl_by_tag(acls, tag_name)

    if raw:
        return acls

    else:
        return _get_formatted_output_macip_acls(acls)


@_verify('ip')
def show_interfaces(raw: bool):
    vpp = VPPControl()
    interfaces_dump = vpp.api.acl_interface_list_dump()
    interfaces: list[dict] = _get_raw_output_interfaces(interfaces_dump)

    if raw:
        return interfaces

    else:
        return _get_formatted_output_interfaces(vpp, interfaces)


@_verify('macip')
def show_macip_interfaces(raw: bool):
    vpp = VPPControl()
    interfaces_dump = vpp.api.macip_acl_interface_list_dump()
    interfaces: list[dict] = _get_raw_output_interfaces(interfaces_dump)

    if raw:
        return interfaces

    else:
        return _get_formatted_output_macip_interfaces(vpp, interfaces)


@_verify('no_target')
def show_all_acls(raw: bool):
    conf = Config()
    acls_all = {}
    path = ['vpp', 'acl']
    if conf.exists(path + ['ip']):
        ip_acls = show_ip_acls(raw, tag_name=None)
        acls_all['ip'] = ip_acls
    if conf.exists(path + ['macip']):
        macip_acls = show_macip_acls(raw, tag_name=None)
        acls_all['macip'] = macip_acls

    if raw:
        return acls_all


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
