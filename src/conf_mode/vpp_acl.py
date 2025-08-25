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

import ipaddress

from vyos import ConfigError

from vyos.configdiff import Diff
from vyos.configdict import node_changed
from vyos.config import Config
from vyos.utils.network import get_protocol_by_name

from vyos.vpp.utils import cli_ifaces_list
from vyos.vpp.acl import Acl


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

# ACL action flags
action_map = {
    'deny': 0,
    'permit': 1,
    'permit-reflect': 2,
}


def get_tcp_mask_value(set_flags, unset_flags):
    mask = 0
    value = 0

    for flag in set_flags + unset_flags:
        bit = TCP_FLAGS.get(flag.upper())
        mask |= bit
        if flag in set_flags:
            value |= bit

    return mask, value


def get_port_first_last(port_range, protocol):
    first_port = 0
    last_port = 65535
    if not port_range:
        if protocol in ['icmp', 'ipv6-icmp']:
            last_port = 255
    elif '-' not in port_range:
        first_port = last_port = port_range
    else:
        first_port, last_port = port_range.split('-')
    return int(first_port), int(last_port)


def create_ip_rules_list(rules):
    rules_list = []
    for rule in rules.values():
        r = {
            'is_permit': action_map[rule.get('action')],
            'src_prefix': rule.get('source', {}).get('prefix', ''),
            'dst_prefix': rule.get('destination', {}).get('prefix', ''),
            'proto': (
                int(get_protocol_by_name(rule.get('protocol')))
                if rule.get('protocol') != 'all'
                else 0
            ),
        }

        tcp_flags = rule.get('tcp_flags', {})
        set_flags = [flag for flag in tcp_flags if flag != 'not']
        unet_flags = list(tcp_flags.get('not', {}).keys())
        tcp_mask, tcp_value = get_tcp_mask_value(set_flags, unet_flags)
        r['tcp_flags_mask'] = tcp_mask
        r['tcp_flags_value'] = tcp_value

        src_ports = rule.get('source', {}).get('port')
        src_first_port, src_last_port = get_port_first_last(
            src_ports, rule.get('protocol')
        )
        r['srcport_or_icmptype_first'] = src_first_port
        r['srcport_or_icmptype_last'] = src_last_port

        dst_ports = rule.get('destination', {}).get('port')
        dst_first_port, dst_last_port = get_port_first_last(
            dst_ports, rule.get('protocol')
        )
        r['dstport_or_icmpcode_first'] = dst_first_port
        r['dstport_or_icmpcode_last'] = dst_last_port

        rules_list.append(r)

    return rules_list


def create_macip_rules_list(rules):
    rules_list = []
    for rule in rules.values():
        r = {
            'is_permit': action_map[rule.get('action')],
            'src_prefix': rule.get('prefix', ''),
            'src_mac': rule.get('mac_address', ''),
            'src_mac_mask': rule.get('mac_mask', ''),
        }
        rules_list.append(r)

    return rules_list


def get_config(config=None) -> dict:
    if config:
        conf = config
    else:
        conf = Config()

    base = ['vpp', 'acl']

    # Get config_dict with default values
    config = conf.get_config_dict(
        base,
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_defaults=True,
        with_recursive_defaults=True,
    )

    if not conf.exists(['vpp']):
        config['remove_vpp'] = True
        return config

    # Get effective config as we need full dictionary for deletion
    effective_config = conf.get_config_dict(
        base,
        key_mangling=('-', '_'),
        effective=True,
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    if not config:
        config['remove'] = True

    changed_ip_ifaces = node_changed(
        conf,
        base + ['ip', 'interface'],
        key_mangling=('-', '_'),
        recursive=True,
        expand_nodes=Diff.DELETE | Diff.ADD,
    )

    changed_macip_ifaces = node_changed(
        conf,
        base + ['macip', 'interface'],
        key_mangling=('-', '_'),
        recursive=True,
        expand_nodes=Diff.DELETE | Diff.ADD,
    )

    config.update(
        {
            'changed_ip_ifaces': changed_ip_ifaces,
            'changed_macip_ifaces': changed_macip_ifaces,
            'vpp_ifaces': cli_ifaces_list(conf),
        }
    )

    if effective_config:
        config.update({'effective': effective_config})

    return config


def verify(config):
    if 'remove' in config or 'remove_vpp' in config:
        return None

    for acl_type in ['ip', 'macip']:
        if acl_type in config:
            acl = config.get(acl_type)
            if 'tag_name' not in acl:
                raise ConfigError(f'"tag-name" is required for "acl {acl_type}"')

            for acl_name, acl_config in acl.get('tag_name').items():
                if 'rule' not in acl_config:
                    raise ConfigError(f'Rules must be configured for ACL {acl_name}')

                for rule, rule_config in acl_config.get('rule').items():
                    err_msg = f'Configuration error for {acl_type} ACL {acl_name} in rule {rule}:'
                    if 'action' not in rule_config:
                        raise ConfigError(f'{err_msg} action must be defined')

            for iface, iface_config in acl.get('interface', {}).items():
                if iface not in config.get('vpp_ifaces'):
                    raise ConfigError(
                        f'{iface} must be a VPP interface for ACL interface'
                    )

    if 'ip' in config:
        acl = config.get('ip')
        for acl_name, acl_config in acl.get('tag_name').items():
            for rule, rule_config in acl_config.get('rule').items():
                err_msg = (
                    f'Configuration error for {acl_type} ACL {acl_name} in rule {rule}:'
                )

                # verify IPv4 and IPv6 address family
                src_prefix = rule_config.get('source', {}).get('prefix')
                dst_prefix = rule_config.get('destination', {}).get('prefix')
                src = ipaddress.ip_network(src_prefix) if src_prefix else None
                dst = ipaddress.ip_network(dst_prefix) if dst_prefix else None

                if src and dst:
                    if src.version != dst.version:
                        raise ConfigError(
                            f'{err_msg} source and destination prefixes must be from the same IP family'
                        )
                elif src or dst:
                    family = src.version if src else dst.version
                    if family == 6:
                        raise ConfigError(
                            f'{err_msg} both source and destination prefixes must be defined for IPv6'
                        )

                # verify protocol
                protocol = rule_config.get('protocol')
                if protocol != 'all':
                    proto = get_protocol_by_name(protocol)
                    if not isinstance(proto, int) and (
                        not proto.isdigit() or int(proto) > 147
                    ):
                        raise ConfigError(
                            f'{err_msg} protocol name {protocol} is not valid'
                        )

                # verify TCP flags
                if 'tcp_flags' in rule_config:
                    if rule_config.get('protocol') != 'tcp':
                        raise ConfigError(
                            f'{err_msg} protocol must be tcp when specifying tcp flags'
                        )

                    not_flags = rule_config.get('tcp_flags').get('not', [])
                    if not_flags:
                        duplicates = [
                            flag
                            for flag in rule_config.get('tcp_flags')
                            if flag in not_flags
                        ]
                        if duplicates:
                            raise ConfigError(
                                f'{err_msg} cannot match a tcp flag as set and not set: {duplicates}'
                            )

        for iface, iface_config in acl.get('interface', {}).items():
            if not any(key in iface_config for key in ('input', 'output')):
                raise ConfigError(
                    f'Please specify direction input/output for interface {iface}'
                )

            for direction in ['input', 'output']:
                if direction in iface_config:
                    iface_acl = iface_config.get(direction)
                    if 'acl_tag' not in iface_acl:
                        raise ConfigError(
                            f'"acl-tag" is required for {direction} interface {iface}'
                        )

                    used_names = []
                    for tag, tag_conf in iface_acl.get('acl_tag').items():
                        if 'tag_name' not in tag_conf:
                            raise ConfigError(
                                f'"tag-name" is required for {direction} interface {iface} with acl-tag {tag}'
                            )
                        name = tag_conf.get('tag_name')
                        if name not in acl.get('tag_name').keys():
                            raise ConfigError(
                                f'ACL with tag-name {name} does not exist. '
                                f'Cannot use it for {direction} interface {iface}'
                            )
                        if name in used_names:
                            raise ConfigError(
                                f'ACL with tag-name {name} is already used for {direction} interface {iface}'
                            )
                        used_names.append(name)

    if 'macip' in config:
        acl = config.get('macip')
        for iface, iface_config in acl.get('interface', {}).items():
            if 'tag_name' not in iface_config:
                raise ConfigError(f'"tag-name" is required for interface {iface}')
            name = iface_config.get('tag_name')
            if name not in acl.get('tag_name').keys():
                raise ConfigError(
                    f'ACL with tag-name {name} does not exist. Cannot use it for interface {iface}'
                )


def generate(config):
    pass


def apply(config):
    if 'remove_vpp' in config:
        return None

    acl = Acl()

    if 'effective' in config:
        # Delete ACL ip
        if 'ip' in config.get('effective'):
            remove_config_ip = config.get('effective').get('ip')

            # Delete ACL interfaces
            for interface in config.get('changed_ip_ifaces'):
                acl.delete_acl_interface(interface)

            # Delete ACLs
            for acl_name in remove_config_ip.get('tag_name'):
                if acl_name not in config.get('ip', {}).get('tag_name', {}):
                    acl.delete_acl(acl_name)

        # Delete ACL macip
        if 'macip' in config.get('effective'):
            remove_config_macip = config.get('effective').get('macip')

            # Delete ACL interfaces
            for interface in config.get('changed_macip_ifaces'):
                acl.delete_acl_macip_interface(interface)

            # Delete ACL macip
            for acl_name in remove_config_macip.get('tag_name'):
                if acl_name not in config.get('macip', {}).get('tag_name', {}):
                    acl.delete_acl_macip(acl_name)

    if 'remove' in config:
        return None

    # Add or replace ACL ip
    config_ip = config.get('ip', {})
    for acl_name in config_ip.get('tag_name', {}):
        rules = create_ip_rules_list(
            config_ip.get('tag_name').get(acl_name).get('rule')
        )
        acl.add_replace_acl(acl_name, rules)

    for iface, iface_config in config_ip.get('interface', {}).items():
        input_tags = [
            v['tag_name']
            for v in iface_config.get('input', {}).get('acl_tag', {}).values()
        ]
        output_tags = [
            v['tag_name']
            for v in iface_config.get('output', {}).get('acl_tag', {}).values()
        ]
        acl.add_acl_interface(iface, input_tags, output_tags)

    # Add or replace ACL macip
    config_macip = config.get('macip', {})
    for acl_name in config_macip.get('tag_name', {}):
        rules = create_macip_rules_list(
            config_macip.get('tag_name').get(acl_name).get('rule')
        )
        acl.add_replace_acl_macip(acl_name, rules)

    for iface, iface_config in config_macip.get('interface', {}).items():
        acl.add_acl_macip_interface(iface, iface_config.get('tag_name'))


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
