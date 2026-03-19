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
from vyos.configdep import set_dependents, call_dependents
from vyos import ConfigError
from vyos.utils.assertion import assert_mac
from vyos.utils.process import is_systemd_service_active

from vyos.ifconfig.vpp import VPPBondInterface
from vyos.vpp.config_deps import deps_bond_dict
from vyos.vpp.config_deps import deps_bridge_dict
from vyos.vpp.config_deps import deps_xconnect_dict
from vyos.vpp.config_verify import verify_vpp_remove_bridge_interface
from vyos.vpp.config_verify import verify_vpp_remove_xconnect_interface
from vyos.vpp.utils import cli_ifaces_list


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

    return lb_mapping.get(lb_name, 0)


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

    base = ['interfaces', 'vpp', 'bonding']

    ifname, config = get_interface_dict(conf, base)

    # Get pppoe-server interfaces
    config['pppoe_ifaces'] = conf.list_nodes(['service', 'pppoe-server', 'interface'])

    if not conf.exists(['vpp']) and not conf.exists(base):
        config['remove_vpp'] = True
        return config

    config['vpp_ifaces'] = cli_ifaces_list(conf, 'candidate')

    # convert values to VPP compatible
    if 'mode' in config:
        config['mode'] = _get_bond_mode(config['mode'])
    if 'hash_policy' in config:
        config['hash_policy'] = _get_bond_lb(config['hash_policy'])

    # Get 'vpp settings' config with default values
    config['vpp_settings'] = conf.get_config_dict(
        ['vpp', 'settings'],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    config['bond_members'] = deps_bond_dict(conf)

    # Dependency
    config['xconn_members'] = deps_xconnect_dict(conf)
    if ifname in config['xconn_members']:
        for xconn_iface in config['xconn_members'][ifname]:
            set_dependents('vpp_interfaces_xconnect', conf, xconn_iface)

    config['bridge_members'] = deps_bridge_dict(conf)
    if ifname in config['bridge_members']:
        for bridge_iface in config['bridge_members'][ifname]:
            set_dependents('vpp_interfaces_bridge', conf, bridge_iface)

    # PPPoE dependency
    if any(i == ifname or i.startswith(f'{ifname}.') for i in config['pppoe_ifaces']):
        set_dependents('pppoe_server', conf)

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

    return config


def verify(config):
    ifname = config['ifname']
    if 'deleted' in config and any(
        i == ifname or i.startswith(f'{ifname}.')
        for i in config.get('pppoe_ifaces', [])
    ):
        raise ConfigError(
            'Cannot remove interface: it is still in use by the PPPoE server'
        )

    if 'remove_vpp' in config:
        return None

    verify_vpp_remove_xconnect_interface(config)
    verify_vpp_remove_bridge_interface(config)

    if 'deleted' in config:
        return None

    if not is_systemd_service_active('vpp.service'):
        raise ConfigError(
            'Cannot configure VPP bonding interface: vpp.service is not running'
        )

    # Member must belong to VPP
    for iface in config.get('member', {}).get('interface', []):
        if iface not in config['vpp_ifaces']:
            raise ConfigError(f'{iface} must be a VPP interface for bonding')

        # Each interface can belong only to one bond
        bond_members = config['bond_members'][iface]
        if len(bond_members) > 1:
            raise ConfigError(
                f'Interface {iface} cannot be a member of multiple bonding interfaces: {", ".join(bond_members)}'
            )

        # Interface cannot be a member of a bridge and a bond at the same time
        bridge_members = config['bridge_members'].get(iface)
        if bridge_members:
            raise ConfigError(
                f'Interface {iface} cannot be a member of a bond because '
                f'it already belongs to bridge interface: {", ".join(bridge_members)}.'
            )

    if 'mac' in config:
        mac = config['mac']
        try:
            assert_mac(mac, test_all_zero=False)
        except:
            raise ConfigError(
                f'Cannot use {mac}: it is a multicast MAC address. Please provide a unicast MAC address.'
            )

    for vif_remove in config.get('vif_remove', []):
        vif_iface = f'{ifname}.{vif_remove}'
        if vif_iface in config.get('pppoe_ifaces', []):
            raise ConfigError(
                f'Cannot remove interface {vif_iface}: it is still in use by the PPPoE server'
            )


def generate(config):
    pass


def apply(config):
    if 'remove_vpp' in config:
        return None

    ifname = config.get('ifname')
    bond = VPPBondInterface(ifname, config)
    bond.remove()

    if 'deleted' in config:
        return

    bond.update(config)

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
