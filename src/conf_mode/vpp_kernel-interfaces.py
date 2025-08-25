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
from vyos.configdict import node_changed
from vyos import ConfigError
from vyos.ifconfig import Interface
from vyos.utils.network import interface_exists
from vyos.utils.process import call
from vyos.vpp import VPPControl


def get_config(config=None) -> dict:
    if config:
        conf = config
    else:
        conf = Config()

    base = ['vpp', 'kernel-interfaces']

    ifname = os.environ['VYOS_TAGNODE_VALUE']

    # Get config_dict with default values
    config = conf.get_config_dict(
        base + [ifname],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_defaults=True,
    )

    if not conf.exists(['vpp']):
        config['remove_vpp'] = True
        return config

    # Get effective config as we need full dicitonary per interface delete
    if __name__ == '__main__':
        effective_config = conf.get_config_dict(
            base + [ifname],
            key_mangling=('-', '_'),
            effective=True,
            get_first_key=True,
            no_tag_node_value_mangle=True,
        )
    # if a file was started as dependency, we are starting from empty config
    else:
        effective_config = {}

    if effective_config:
        config.update({'effective': effective_config})

    address_removed = leaf_node_changed(conf, base + [ifname, 'address'])
    if address_removed:
        config['address_removed'] = address_removed

    description_removed = leaf_node_changed(conf, base + [ifname, 'description'])
    if description_removed:
        config['description_removed'] = {}

    vlans_removed = node_changed(conf, base + [ifname, 'vif'])
    if vlans_removed:
        config['vlans_removed'] = vlans_removed

    config['ifname'] = ifname

    return config


def verify(config):
    if 'remove' in config or 'remove_vpp' in config:
        return None

    # Interface must exists before it is configured
    if not interface_exists(config['ifname']):
        raise ConfigError(
            f'Interface {config["ifname"]} must be created before using in configuration'
        )


def generate(config):
    pass


def apply(config):
    if 'remove_vpp' in config:
        return None

    ifname = config.get('ifname')
    i = Interface(ifname)
    # update/remove addresses
    if 'address_removed' in config:
        for address in config['address_removed']:
            i.del_addr(address)
    # remove description
    if 'description_removed' in config:
        i.set_alias('')

    # remove VLANs
    if 'vlans_removed' in config:
        for vlan in config['vlans_removed']:
            call(f'ip link del dev {ifname}.{vlan}')

    # Delete
    if 'remove' in config:
        pass
    else:
        # Add address
        if 'address' in config:
            for address in config['address']:
                i.add_addr(address)
        # Set MTU
        if 'mtu' in config:
            i.set_mtu(config.get('mtu'))
        # Set description
        if 'description' in config:
            i.set_alias(config.get('description'))
        # Admin state down
        if 'disable' in config:
            i.set_admin_state('down')
        else:
            i.set_admin_state('up')

        for vlan, vlan_config in config.get('vif', {}).items():
            if vlan not in config.get('effective', {}).get('vif', {}).keys():
                call(
                    f'ip link add link {ifname} name {ifname}.{vlan} type vlan id {vlan}'
                )
                call(f'ip link set dev {ifname}.{vlan} up')
            v = Interface(f'{ifname}.{vlan}')

            # VLAN address
            addresses_effective = (
                config.get('effective', {})
                .get('vif', {})
                .get(vlan, {})
                .get('address', [])
            )
            addresses_candidate = vlan_config.get('address', [])

            for ipaddr in addresses_effective:
                if ipaddr not in addresses_candidate:
                    v.del_addr(ipaddr)
            for ipaddr in addresses_candidate:
                if ipaddr not in addresses_effective:
                    v.add_addr(ipaddr)

            # VLAN description
            description_effective = (
                config.get('effective', {})
                .get('vif', {})
                .get(vlan, {})
                .get('description', '')
            )
            description_candidate = vlan_config.get('description', '')

            if description_candidate:
                v.set_alias(description_candidate)
            elif description_effective and not description_candidate:
                v.set_alias('')

            v.set_admin_state('up')

    # Set rx-mode
    rx_mode = config.get('rx_mode')
    if rx_mode:
        vpp_control = VPPControl()
        lcp_name = vpp_control.lcp_pair_find(kernel_name=ifname).get('vpp_name_kernel')
        vpp_control.iface_rxmode(lcp_name, rx_mode)

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
