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
from vyos.configdict import get_interface_dict
from vyos import ConfigError
from vyos.utils.process import is_systemd_service_active

from vyos.ifconfig.vpp import VPPBridgeInterface
from vyos.vpp.config_deps import deps_bond_dict
from vyos.vpp.config_deps import deps_bridge_dict
from vyos.vpp.config_deps import deps_xconnect_dict
from vyos.vpp.config_verify import verify_member_conflicts
from vyos.vpp.config_verify import verify_vpp_interface_not_in_feature


def get_config(config=None) -> dict:
    """Get Bridge interface configuration

    Args:
        config (vyos.config.Config, optional): The VyOS configuration dictionary
    Returns:
        dict: Bridge interface configuration
    """
    if config:
        conf = config
    else:
        conf = Config()

    base = ['interfaces', 'vpp', 'bridge']

    ifname, config = get_interface_dict(conf, base)

    if not conf.exists(['vpp']) and not conf.exists(base):
        config['remove_vpp'] = True
        return config

    # Get global vpp interfaces for verify
    config['vpp_interfaces'] = conf.get_config_dict(
        ['vpp', 'settings', 'interface'],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    # Get all gre interfaces config
    config['gre_interfaces'] = conf.get_config_dict(
        ['interfaces', 'vpp', 'gre'],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_defaults=True,
        with_recursive_defaults=True,
    )

    config['bond_members'] = deps_bond_dict(conf)
    config['bridge_members'] = deps_bridge_dict(conf)
    config['xconn_members'] = deps_xconnect_dict(conf)

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
            'Cannot configure VPP bridge interface: vpp.service is not running'
        )

    # Check if interface exists in vpp before adding to bridge-domain
    allowed_prefixes = ('vppbond', 'vppgre', 'vpplo', 'vppvxlan')

    if 'member' in config:
        bvi_exists = False
        for member, member_config in (
            config.get('member', {}).get('interface', {}).items()
        ):
            # Check if the interface exists in VPP settings or starts with allowed prefixes
            if not (
                member in config.get('vpp_interfaces', {})
                or member.startswith(allowed_prefixes)
            ):
                raise ConfigError(
                    f"Interface '{member}' not found in 'vpp settings interface' or does not start with allowed prefixes {allowed_prefixes}"
                )

            # Each interface can belong only to one bridge
            bridge_members = config['bridge_members'][member]
            if len(bridge_members) > 1:
                raise ConfigError(
                    f'Interface {member} is added to more than one bridge: {", ".join(bridge_members)}'
                )

            verify_member_conflicts(member, config, 'bridge')
            verify_vpp_interface_not_in_feature(member, config.get('vpp'))

            # Check if BVI is already defined, only one BVI per bridge domain is allowed
            if 'bvi' in member_config:
                if bvi_exists:
                    raise ConfigError("Only one BVI per bridge domain is allowed")
                if not member.startswith('vpplo'):
                    raise ConfigError("BVI can only be defined on loopback interface")
                bvi_exists = True

        # check GRE tunnels as part of the bridge, only tunnel-type "teb" is allowed
        #   set interfaces vpp bridge vppbr1 member interface vppgre1
        #   set interfaces vpp gre vppgre1 tunnel-type teb
        if member.startswith('vppgre'):
            if member in config.get('gre_interfaces'):
                gre_config = config.get('gre_interfaces').get(member)
                if gre_config.get('tunnel_type') != 'teb':
                    raise ConfigError(
                        f'GRE interface "{member}" in bridge must have tunnel-type "teb". '
                        f'Current tunnel-type is "{gre_config.get("tunnel_type")}".'
                    )


def generate(config):
    pass


def apply(config):
    if 'remove_vpp' in config:
        return None

    ifname = config.get('ifname')
    bridge = VPPBridgeInterface(ifname)
    bridge.remove()

    if 'deleted' in config:
        return

    bridge.update(config)

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
