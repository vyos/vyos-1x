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

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configdep import set_dependents, call_dependents
from vyos.utils.process import is_systemd_service_active

from vyos.ifconfig.vpp import VPPVXLANInterface
from vyos.vpp.config_deps import deps_bridge_dict
from vyos.vpp.config_deps import deps_xconnect_dict
from vyos.vpp.config_verify import verify_vpp_remove_bridge_interface
from vyos.vpp.config_verify import verify_vpp_remove_xconnect_interface
from vyos.vpp.config_verify import verify_vpp_tunnel_source_address
from vyos.vpp.utils import cli_ethernet_with_vifs_ifaces


def get_config(config=None) -> dict:
    """Get VXLAN interface configuration

    Args:
        config (vyos.config.Config, optional): The VyOS configuration dictionary
    Returns:
        dict: VXLAN interface configuration
    """
    if config:
        conf = config
    else:
        conf = Config()

    base = ['interfaces', 'vpp', 'vxlan']

    ifname, config = get_interface_dict(conf, base)

    if not conf.exists(['vpp']) and not conf.exists(base):
        config['remove_vpp'] = True
        return config

    # list of all Ethernet interfaces with vifs
    config['vpp_ether_vif_ifaces'] = cli_ethernet_with_vifs_ifaces(conf)

    # Dependency
    config['xconn_members'] = deps_xconnect_dict(conf)
    if ifname in config['xconn_members']:
        for xconn_iface in config['xconn_members'][ifname]:
            set_dependents('vpp_interfaces_xconnect', conf, xconn_iface)

    config['bridge_members'] = deps_bridge_dict(conf)
    if ifname in config['bridge_members']:
        for bridge_iface in config['bridge_members'][ifname]:
            set_dependents('vpp_interfaces_bridge', conf, bridge_iface)

    # Get 'vpp settings' config with default values
    config['vpp_settings'] = conf.get_config_dict(
        ['vpp', 'settings'],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_defaults=True,
    )

    # NAT dependency
    if conf.exists(['vpp', 'nat', 'nat44']):
        set_dependents('vpp_nat_nat44', conf)
    if conf.exists(['vpp', 'nat', 'cgnat']):
        set_dependents('vpp_nat_cgnat', conf)

    # ACL dependency
    if conf.exists(['vpp', 'acl']):
        set_dependents('vpp_acl', conf)

    return config


def verify(config):
    # No need to verify anything if vpp is removed
    if 'remove_vpp' in config:
        return None

    verify_vpp_remove_xconnect_interface(config)
    verify_vpp_remove_bridge_interface(config)

    if 'deleted' in config:
        return None

    if not is_systemd_service_active('vpp.service'):
        raise ConfigError(
            'Cannot configure VPP vxlan interface: vpp.service is not running'
        )

    required_keys = {'source_address', 'remote', 'vni'}
    if not all(key in config for key in required_keys):
        missing_keys = required_keys - set(config.keys())
        raise ConfigError(
            f"Required options are missing: {', '.join(missing_keys).replace('_', '-')}"
        )

    # verify source address and remote address
    verify_vpp_tunnel_source_address(config)
    if config.get('source_address') == config.get('remote'):
        raise ConfigError('Remote address must not be the same as source address')


def generate(config):
    pass


def apply(config):
    if 'remove_vpp' in config:
        return None

    ifname = config.get('ifname')
    # Delete interface
    vxlan = VPPVXLANInterface(ifname, config)
    vxlan.remove()

    if 'deleted' in config:
        return None

    vxlan.update(config)

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
