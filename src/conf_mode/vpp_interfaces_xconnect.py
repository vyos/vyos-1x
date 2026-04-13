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

from vyos.config import Config
from vyos import ConfigError
from vyos.configdict import get_interface_dict
from vyos.utils.process import is_systemd_service_active

from vyos.ifconfig.vpp import VPPXconnectInterface
from vyos.vpp.config_deps import deps_bond_dict
from vyos.vpp.config_deps import deps_bridge_dict
from vyos.vpp.config_deps import deps_xconnect_dict
from vyos.vpp.config_verify import verify_member_conflicts
from vyos.vpp.config_verify import verify_vpp_interface_not_in_feature
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

    base = ['interfaces', 'vpp', 'xconnect']

    ifname, config = get_interface_dict(conf, base)

    if not conf.exists(['vpp']) and not conf.exists(base):
        config['remove_vpp'] = True
        return config

    # Get effective config as we need full dictionary per interface delete
    effective_config = conf.get_config_dict(
        base + [ifname],
        key_mangling=('-', '_'),
        effective=True,
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    if effective_config:
        config.update({'effective': effective_config})

    config['bond_members'] = deps_bond_dict(conf)
    config['bridge_members'] = deps_bridge_dict(conf)
    config['xconn_members'] = deps_xconnect_dict(conf)
    config['vpp_ifaces'] = cli_ifaces_list(conf, 'candidate')

    # VPP config for member-in-feature checks
    config['vpp'] = conf.get_config_dict(
        ['vpp'],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    return config


def verify(config):
    if 'deleted' in config or 'remove_vpp' in config:
        return None

    if not is_systemd_service_active('vpp.service'):
        raise ConfigError(
            'Cannot configure layer 2 cross-connect: vpp.service is not running'
        )

    # Xconnect requires 2 members
    if len(config.get('member', {}).get('interface')) != 2:
        raise ConfigError('Cross connect requires 2 members')

    not_allowed_prefixes = ('vppbond', 'vppbr', 'vpplo')
    for iface in config.get('member', {}).get('interface', []):
        # Ensure the interface is allowed as xconnect member
        if iface.startswith(not_allowed_prefixes):
            raise ConfigError(f'{iface} cannot be configured as xconnect member')
        # Member must belong to VPP
        if iface not in config['vpp_ifaces']:
            raise ConfigError(f'{iface} must be a VPP interface for xconnect')

        # Each interface can belong only to one xconnect
        xconn_members = config['xconn_members'][iface]
        if len(xconn_members) > 1:
            raise ConfigError(
                f'Interface {iface} added to more than one xconnect: {", ".join(xconn_members)}'
            )

        verify_member_conflicts(iface, config, 'xconn')
        verify_vpp_interface_not_in_feature(iface, config.get('vpp'))


def generate(config):
    pass


def apply(config):
    if 'remove_vpp' in config:
        return None

    ifname = config.get('ifname')
    xconnect = VPPXconnectInterface(ifname)

    # Delete xconnect
    if 'effective' in config:
        remove_config = config.get('effective')
        members = remove_config['member']['interface']
        xconnect.remove(members)

    if 'deleted' in config:
        return None

    # Add xconnect
    xconnect.update(config)

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
