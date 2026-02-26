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

import os

from vyos.config import Config
from vyos.configdict import leaf_node_changed
from vyos.configdep import set_dependents, call_dependents
from vyos import ConfigError

from vyos.vpp.interface import BondInterface
from vyos.vpp.config_deps import deps_xconnect_dict
from vyos.vpp.config_verify import (
    verify_vpp_remove_xconnect_interface,
    verify_vpp_remove_kernel_interface,
    verify_vpp_change_kernel_interface,
    verify_vpp_exists_kernel_interface,
)
from vyos.vpp.utils import cli_ifaces_list, cli_ifaces_lcp_kernel_list


def _get_bond_mode(mode_name: str) -> int:
    """Convert VyOS CLI name bonding mode to VPP compatible"""
    mode_mapping = {
        'round-robin': 1,
        'active-backup': 2,
        'xor-hash': 3,
        'broadcast': 4,
        '802.3ad': 5,
    }

    return mode_mapping.get(mode_name, 5)


def _get_bond_lb(lb_name: str) -> int:
    """Convert VyOS CLI name bonding load balance to VPP compatible"""
    lb_mapping = {
        'layer2': 0,
        'layer2+3': 2,
        'layer3+4': 1,
    }

    return lb_mapping.get(lb_name, 5)


def get_config(config=None) -> dict:
    """Get Bonding interface configuration

    Args:
        config (vyos.config.Config, optional): The VyOS configuration dictionary
    Returns:
        dict: Bonding interface configuration
    """
    if config:
        conf = config
    else:
        conf = Config()

    base = ['vpp', 'interfaces', 'bonding']
    base_kernel_interfaces = ['vpp', 'kernel-interfaces']

    ifname = os.environ['VYOS_TAGNODE_VALUE']

    # Get config_dict with default values
    config = conf.get_config_dict(
        base + [ifname],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_defaults=True,
        with_recursive_defaults=True,
    )

    if not conf.exists(['vpp']):
        config['remove_vpp'] = True
        return config

    # Get effective config as we need full dicitonary per interface delete
    effective_config = conf.get_config_dict(
        base + [ifname],
        key_mangling=('-', '_'),
        effective=True,
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    if effective_config:
        config.update({'effective': effective_config})

    if not conf.exists(base + [ifname]):
        config['remove'] = True

    if effective_config:
        config.update({'effective': effective_config})

    config['vpp_ifaces'] = cli_ifaces_list(conf, 'candidate')

    # Get global 'vpp kernel-interfaces' for verify
    config['vpp_kernel_interfaces'] = conf.get_config_dict(
        base_kernel_interfaces,
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    # list of all kernel interfaces `vpp interface xxx kernel-interface xxx`
    config['candidate_kernel_interfaces'] = cli_ifaces_lcp_kernel_list(conf)

    # convert values to VPP compatible
    if 'mode' in config:
        config['mode'] = _get_bond_mode(config['mode'])
    if 'hash_policy' in config:
        config['hash_policy'] = _get_bond_lb(config['hash_policy'])

    tmp = leaf_node_changed(conf, base + [ifname, 'kernel-interface'])
    if tmp:
        config['kernel_interface_removed'] = tmp

    # Dependency
    config['xconn_members'] = deps_xconnect_dict(conf)
    if ifname in config['xconn_members']:
        for xconn_iface in config['xconn_members'][ifname]:
            set_dependents('vpp_interfaces_xconnect', conf, xconn_iface)

    if conf.exists(base + [ifname, 'kernel-interface']):
        if effective_config.get('kernel_interface') or __name__ != '__main__':
            iface = config.get('kernel_interface')
            if conf.exists(['vpp', 'kernel-interfaces', iface]):
                set_dependents('vpp_kernel_interface', conf, iface)

    # NAT dependency
    if conf.exists(['vpp', 'nat', 'nat44']):
        set_dependents('vpp_nat_nat44', conf)
    if conf.exists(['vpp', 'nat', 'cgnat']):
        set_dependents('vpp_nat_cgnat', conf)

    # ACL dependency
    if conf.exists(['vpp', 'acl']):
        set_dependents('vpp_acl', conf)

    # IPFIX dependency
    if conf.exists(['vpp', 'ipfix']):
        set_dependents('vpp_ipfix', conf)

    config['ifname'] = ifname

    return config


def verify(config):
    if 'remove_vpp' in config:
        return None

    verify_vpp_remove_kernel_interface(config)
    verify_vpp_remove_xconnect_interface(config)

    # Member must belong to VPP
    for iface in config.get('member', {}).get('interface', []):
        if iface not in config['vpp_ifaces']:
            raise ConfigError(f'{iface} must be a VPP interface for bonding')

    if 'remove' in config:
        return None

    verify_vpp_change_kernel_interface(config)
    verify_vpp_exists_kernel_interface(config)


def generate(config):
    pass


def apply(config):
    if 'remove_vpp' in config:
        return None

    ifname = config.get('ifname')
    # remove old members
    if 'effective' in config:
        members = config['effective'].get('member', {}).get('interface', [])

        kernel_interface = config['effective'].get('kernel_interface', '')
        i = BondInterface(ifname, kernel_interface=kernel_interface)
        for member in members:
            i.detach_member(interface=member)

        if 'kernel_interface' in config['effective'] and i.lcp_pair_exists():
            i.kernel_delete()
        # Delete bonding interface
        i.delete()

    if 'remove' in config:
        return None

    # Create a new one
    mode = config.get('mode')
    lb = config.get('hash_policy')
    members = config.get('member', {}).get('interface', [])
    mac = config.get('mac', '')
    kernel_interface = config.get('kernel_interface', '')
    state = 'up' if 'disable' not in config else 'down'

    i = BondInterface(ifname, mode, lb, mac, kernel_interface, state)
    i.add()
    # Add members to bond
    if members:
        for member in members:
            i.add_member(interface=member)

    call_dependents()

    return None


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
