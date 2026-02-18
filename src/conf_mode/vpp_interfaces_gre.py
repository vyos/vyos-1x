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

from vyos import ConfigError

from vyos.config import Config
from vyos.configdict import leaf_node_changed
from vyos.configdep import set_dependents, call_dependents
from vyos.template import is_interface

from vyos.vpp.interface import GREInterface
from vyos.vpp.config_deps import deps_xconnect_dict
from vyos.vpp.config_verify import (
    verify_vpp_remove_kernel_interface,
    verify_vpp_change_kernel_interface,
    verify_vpp_remove_xconnect_interface,
    verify_vpp_exists_kernel_interface,
    verify_vpp_tunnel_source_address,
)
from vyos.vpp.utils import cli_ifaces_lcp_kernel_list, cli_ethernet_with_vifs_ifaces


def get_config(config=None) -> dict:
    """Get GRE interface configuration

    Args:
        config (vyos.config.Config, optional): The VyOS configuration dictionary
    Returns:
        dict: GRE interface configuration
    """
    if config:
        conf = config
    else:
        conf = Config()

    base = ['vpp', 'interfaces', 'gre']
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

    # Get global 'vpp kernel-interfaces' for verify
    config['vpp_kernel_interfaces'] = conf.get_config_dict(
        base_kernel_interfaces,
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    tmp = leaf_node_changed(conf, base + [ifname, 'kernel-interface'])
    if tmp:
        config['kernel_interface_removed'] = tmp

    # list of all kernel interfaces `vpp interface xxx kernel-interface xxx`
    config['candidate_kernel_interfaces'] = cli_ifaces_lcp_kernel_list(conf)

    # list of all Ethernet interfaces with vifs
    config['vpp_ether_vif_ifaces'] = cli_ethernet_with_vifs_ifaces(conf)

    # Dependency
    config['xconn_members'] = deps_xconnect_dict(conf)
    if ifname in config['xconn_members']:
        for xconn_iface in config['xconn_members'][ifname]:
            set_dependents('vpp_interfaces_xconnect', conf, xconn_iface)

    if effective_config.get('kernel_interface'):
        if conf.exists(base + [ifname, 'kernel-interface']):
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

    config['ifname'] = ifname
    return config


def verify(config):
    # No need to verify anything if vpp is removed
    if 'remove_vpp' in config:
        return None

    # Verify that removed kernel interface is not used in 'vpp kernel-interfaces'.
    # vpp interfaces gre greX kernel-interface vpp-tunX
    # vpp kernel-interface vpp-tunX
    verify_vpp_remove_kernel_interface(config)

    verify_vpp_remove_xconnect_interface(config)

    # config removed
    if 'remove' in config:
        return None

    # source-address and remote are mandatory options
    required_keys = {'source_address', 'remote', 'mode', 'tunnel_type'}
    if not all(key in config for key in required_keys):
        missing_keys = required_keys - set(config.keys())
        raise ConfigError(
            f"Required options are missing: {', '.join(missing_keys).replace('_', '-')}"
        )

    # verify source address and remote address
    verify_vpp_tunnel_source_address(config)
    if config.get('source_address') == config.get('remote'):
        raise ConfigError('Remote address must not be the same as source address')

    # check multipoint mode
    if config.get('mode') == 'point-to-multipoint':
        # For multipoint mode, remote IP must be 0.0.0.0
        if config.get('remote') != '0.0.0.0':
            raise ConfigError('For point-to-multipoint mode, remote must be 0.0.0.0')

    # Change 'vpp interfaces gre greX kernel-interface vpp-tunX'
    #     => 'vpp interfaces gre greX kernel-interface vpp-tunY'
    # check if we have kernel interface config 'vpp kernel-interface vpp-tunX'
    verify_vpp_change_kernel_interface(config)
    verify_vpp_exists_kernel_interface(config)


def generate(config):
    pass


def apply(config):
    if 'remove_vpp' in config:
        return None

    ifname = config.get('ifname')
    # Delete interface
    if 'effective' in config:
        remove_config = config.get('effective')
        src_addr = remove_config.get('source_address')
        dst_addr = remove_config.get('remote')
        i = GREInterface(ifname, src_addr, dst_addr)
        i.delete()

    if 'remove' in config:
        return None

    # Add interface
    src_addr = config.get('source_address')
    dst_addr = config.get('remote')
    kernel_interface = config.get('kernel_interface', '')
    mode = config.get('mode')
    tunnel_type = config.get('tunnel_type')
    state = 'up' if 'disable' not in config else 'down'
    i = GREInterface(
        ifname, src_addr, dst_addr, tunnel_type, mode, kernel_interface, state
    )
    i.add()

    # Add kernel-interface (LCP) if interface is not exist
    if 'kernel_interface' in config and not is_interface(kernel_interface):
        i.kernel_add()

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
