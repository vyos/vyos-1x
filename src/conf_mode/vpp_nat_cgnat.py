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

from vyos import ConfigError
from vyos.config import Config, config_dict_merge
from vyos.configdict import node_changed
from vyos.configdiff import Diff
from vyos.vpp.utils import cli_ifaces_list
from vyos.vpp.utils import vpp_iface_name_transform

from vyos.vpp.nat.det44 import Det44
from vyos.vpp.control_vpp import VPPControl


def get_config(config=None) -> dict:
    if config:
        conf = config
    else:
        conf = Config()

    base = ['vpp', 'nat', 'cgnat']

    # Get config_dict with default values
    config = conf.get_config_dict(
        base,
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    if not conf.exists(['vpp']):
        config['remove_vpp'] = True
        return config

    # Get effective config as we need full dictionary to delete
    effective_config = conf.get_config_dict(
        base,
        key_mangling=('-', '_'),
        effective=True,
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    if not config:
        config['remove'] = True

    # Get default values which we need to conditionally update into the
    # dictionary retrieved.
    default_values = conf.get_config_defaults(**config.kwargs, recursive=True)
    config = config_dict_merge(default_values, config)

    config_changed = node_changed(
        conf,
        base,
        key_mangling=('-', '_'),
        recursive=True,
        expand_nodes=Diff.DELETE | Diff.ADD,
    )

    changed_rules = node_changed(
        conf,
        base + ['rule'],
        key_mangling=('-', '_'),
        recursive=True,
        expand_nodes=Diff.DELETE | Diff.ADD,
    )

    if not config_changed:
        changed_rules = list(config.get('rule', {}).keys())

    config.update(
        {
            'changed_rules': changed_rules,
            'vpp_ifaces': cli_ifaces_list(conf),
        }
    )

    if effective_config:
        config.update({'effective': effective_config})

    return config


def verify(config):
    if 'remove' in config or 'remove_vpp' in config:
        return None

    if 'interface' not in config:
        raise ConfigError('Interfaces must be configured for CGNAT')
    if 'rule' not in config:
        raise ConfigError('Rules must be configured for CGNAT')

    required_keys = {'inside', 'outside'}
    missing_keys = required_keys - set(config['interface'].keys())
    if missing_keys:
        raise ConfigError(
            f'Both inside and outside interfaces must be configured. '
            f'Please add: {", ".join(missing_keys)}'
        )

    conflict_ifaces = set(config['interface']['inside']).intersection(
        set(config['interface']['outside'])
    )
    if conflict_ifaces:
        raise ConfigError(
            f'Interface cannot be both inside and outside. '
            f'Please choose a side for: {", ".join(conflict_ifaces)} '
        )

    vpp = VPPControl()
    for direction in ['inside', 'outside']:
        for interface in config['interface'][direction]:
            vpp_iface_name = vpp_iface_name_transform(interface)
            if vpp.get_sw_if_index(vpp_iface_name) is None:
                raise ConfigError(
                    f'{interface} must be a VPP interface for {direction} CGNAT interface'
                )

    required_keys = {'outside_prefix', 'inside_prefix'}
    for rule in config['rule']:
        missing_keys = required_keys - set(config['rule'][rule].keys())
        if missing_keys:
            raise ConfigError(
                f'Both inside-prefix and outside-prefix must be configured in rule {rule}. '
                f'Please add: {", ".join(missing_keys).replace("_", "-")}'
            )


def generate(config):
    pass


def apply(config):
    if 'remove_vpp' in config:
        return None

    cgnat = Det44()

    if 'remove' in config:
        cgnat.disable_det44_plugin()
        return None

    if 'effective' in config:
        remove_config = config.get('effective')
        # Delete inside interfaces
        for interface in cgnat.get_det44_interfaces_inside():
            cgnat.delete_det44_interface_inside(interface)
        # Delete outside interfaces
        for interface in cgnat.get_det44_interfaces_outside():
            cgnat.delete_det44_interface_outside(interface)
        # Delete CGNAT rules
        for rule in config['changed_rules']:
            if rule in remove_config.get('rule', {}):
                rule_config = remove_config['rule'][rule]
                in_addr, in_plen = rule_config['inside_prefix'].split('/')
                out_addr, out_plen = rule_config['outside_prefix'].split('/')
                cgnat.delete_det44_mapping(
                    in_addr=in_addr,
                    in_plen=int(in_plen),
                    out_addr=out_addr,
                    out_plen=int(out_plen),
                )

    # Add DET44
    cgnat.enable_det44_plugin()
    # Add inside interfaces
    for interface in config['interface']['inside']:
        vpp_iface_name = vpp_iface_name_transform(interface)
        cgnat.add_det44_interface_inside(vpp_iface_name)
    # Add outside interfaces
    for interface in config['interface']['outside']:
        vpp_iface_name = vpp_iface_name_transform(interface)
        cgnat.add_det44_interface_outside(vpp_iface_name)
    # Add CGNAT rules
    for rule in config['changed_rules']:
        if rule in config.get('rule', {}):
            rule_config = config['rule'][rule]
            in_addr, in_plen = rule_config['inside_prefix'].split('/')
            out_addr, out_plen = rule_config['outside_prefix'].split('/')
            cgnat.add_det44_mapping(
                in_addr=in_addr,
                in_plen=int(in_plen),
                out_addr=out_addr,
                out_plen=int(out_plen),
            )
    # Set CGNAT timeouts
    cgnat.set_det44_timeouts(
        icmp=int(config['timeout']['icmp']),
        udp=int(config['timeout']['udp']),
        tcp_established=int(config['timeout']['tcp_established']),
        tcp_transitory=int(config['timeout']['tcp_transitory']),
    )


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
