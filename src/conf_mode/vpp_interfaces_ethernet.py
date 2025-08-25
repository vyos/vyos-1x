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
from vyos.configdep import set_dependents
from vyos import ConfigError
from vyos.vpp.config_verify import verify_vpp_remove_xconnect_interface


def get_config(config=None) -> dict:
    """Get Ethernet interface configuration

    Args:
        config (vyos.config.Config, optional): The VyOS configuration dictionary
    Returns:
        dict: Ethernet interface configuration
    """
    if config:
        conf = config
    else:
        conf = Config()

    base = ['vpp', 'interfaces', 'ethernet']
    base_interfaces_xconnect = ['vpp', 'interfaces', 'xconnect']

    ifname = os.environ['VYOS_TAGNODE_VALUE']

    # Get effective config as we need full dicitonary per interface delete
    effective_config = conf.get_config_dict(
        base + [ifname],
        key_mangling=('-', '_'),
        effective=True,
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    if not conf.exists(base + [ifname]):
        config = conf.get_config_dict(
            base + [ifname],
            key_mangling=('-', '_'),
            get_first_key=True,
            no_tag_node_value_mangle=True,
        )
        config.update({'remove': effective_config})
    else:
        # Get config_dict with default values
        config = conf.get_config_dict(
            base + [ifname],
            key_mangling=('-', '_'),
            get_first_key=True,
            no_tag_node_value_mangle=True,
            with_defaults=True,
            with_recursive_defaults=True,
        )

    # Get global 'vpp interfaces xconnect'
    config['vpp_interfaces_xconnect'] = conf.get_config_dict(
        base_interfaces_xconnect,
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    # Dependency
    for xcon_name, xcon_config in config.get('vpp_interfaces_xconnect').items():
        for member_name in xcon_config.get('member', {}).get('interface', []):
            if member_name == ifname:
                set_dependents('vpp_interfaces_xconnect', conf, xcon_name)

    if conf.exists(base + [ifname, 'kernel-interface']):
        iface = config.get('kernel_interface')
        if conf.exists(['vpp', 'kernel-interfaces', iface]):
            set_dependents('vpp_kernel_interface', conf, iface)

    config['ifname'] = ifname
    return config


def verify(config):
    verify_vpp_remove_xconnect_interface(config)
    if 'remove' in config:
        return None


def generate(config):
    pass


def apply(config):
    # Delete interface
    if 'remove' in config:
        pass
        # remove_config = config.get('remove')
        # ifname = config.get('ifname')
        # src_addr = remove_config.get('source_address')
        # dst_addr = remove_config.get('remote')
        # vni = int(remove_config.get('vni'))
        # v = VXLANInterface(ifname, src_addr, dst_addr, vni)
        # v.delete()
    else:
        pass
        # ifname = config.get('ifname')
        # kernel_interface = config.get('kernel_interface', '')
        # v = VXLANInterface(ifname, src_addr, dst_addr, vni, kernel_interface)
        # v.add()
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
