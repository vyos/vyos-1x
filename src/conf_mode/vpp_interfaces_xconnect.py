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
from vyos import ConfigError
from vyos.vpp.config_deps import deps_xconnect_dict
from vyos.vpp.interface import XconnectInterface
from vyos.vpp.utils import cli_ifaces_list


def get_config(config=None) -> dict:
    """Get Xconnect interface configuration

    Args:
        config (vyos.config.Config, optional): The VyOS configuration dictionary
    Returns:
        dict: Bridge interface configuration
    """
    if config:
        conf = config
    else:
        conf = Config()

    base = ['vpp', 'interfaces', 'xconnect']
    vpp_interfaces = ['vpp', 'settings', 'interface']

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

    if not config:
        config['remove'] = True

    if effective_config:
        config.update({'effective': effective_config})

    # Get global vpp interfaces for verify
    config['vpp_interfaces'] = conf.get_config_dict(
        vpp_interfaces,
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    config['xconn_members'] = deps_xconnect_dict(conf)
    config['vpp_ifaces'] = cli_ifaces_list(conf, 'candidate')

    config['ifname'] = ifname

    return config


def verify(config):
    if 'remove' in config or 'remove_vpp' in config:
        return None

    # Xconnect requires 2 members
    if len(config.get('member', {}).get('interface')) != 2:
        raise ConfigError('Cross connect requires 2 members')

    # Member must belong to VPP
    for iface in config.get('member', {}).get('interface', []):
        if iface not in config['vpp_ifaces']:
            raise ConfigError(f'{iface} must be a VPP interface for xconnect')

    # Each interface can belong only to one xconnect
    for xconn_member, xconn_ifaces in config['xconn_members'].items():
        if len(xconn_ifaces) > 1:
            raise ConfigError(
                f'Interface {xconn_member} added to more than one xconnect: {xconn_ifaces}'
            )


def generate(config):
    pass


def apply(config):
    if 'remove_vpp' in config:
        return None

    ifname = config.get('ifname')

    # Delete xconnect
    if 'effective' in config:
        remove_config = config.get('effective')
        members = remove_config.get('member', {}).get('interface')
        i = XconnectInterface(ifname, members=members)
        i.del_l2_xconnect()

    if 'remove' in config:
        return None

    # Add xconnect
    members = config.get('member', {}).get('interface')
    state = 'up' if 'disable' not in config else 'down'
    i = XconnectInterface(ifname, members=members, state=state)
    i.add_l2_xconnect()

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
