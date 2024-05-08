#!/usr/bin/env python3
#
# Copyright (C) 2019-2024 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from sys import exit

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configdict import node_changed
from vyos.configdict import is_member
from vyos.configdict import is_source_interface
from vyos.configdict import has_vlan_subinterface_configured
from vyos.configverify import verify_dhcpv6
from vyos.configverify import verify_mirror_redirect
from vyos.configverify import verify_vrf
from vyos.ifconfig import BridgeIf
from vyos.configdict import has_address_configured
from vyos.configdict import has_vrf_configured
from vyos.configdep import set_dependents
from vyos.configdep import call_dependents
from vyos.utils.dict import dict_search
from vyos.utils.network import interface_exists
from vyos import ConfigError

from vyos import airbag
airbag.enable()

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'bridge']
    ifname, bridge = get_interface_dict(conf, base)

    # determine which members have been removed
    tmp = node_changed(conf, base + [ifname, 'member', 'interface'])
    if tmp:
        if 'member' in bridge:
            bridge['member'].update({'interface_remove' : tmp })
        else:
            bridge.update({'member' : {'interface_remove' : tmp }})
            for interface in tmp:
                # When using VXLAN member interfaces that are configured for Single
                # VXLAN Device (SVD) we need to call the VXLAN conf-mode script to
                # re-create VLAN to VNI mappings if required, but only if the interface
                # is already live on the system - this must not be done on first commit
                if interface.startswith('vxlan') and interface_exists(interface):
                    set_dependents('vxlan', conf, interface)
                # When using Wireless member interfaces we need to inform hostapd
                # to properly set-up the bridge
                elif interface.startswith('wlan') and interface_exists(interface):
                    set_dependents('wlan', conf, interface)

    if dict_search('member.interface', bridge) is not None:
        for interface in list(bridge['member']['interface']):
            # Check if member interface is already member of another bridge
            tmp = is_member(conf, interface, 'bridge')
            if tmp and bridge['ifname'] not in tmp:
                bridge['member']['interface'][interface].update({'is_bridge_member' : tmp})

            # Check if member interface is already member of a bond
            tmp = is_member(conf, interface, 'bonding')
            if tmp: bridge['member']['interface'][interface].update({'is_bond_member' : tmp})

            # Check if member interface is used as source-interface on another interface
            tmp = is_source_interface(conf, interface)
            if tmp: bridge['member']['interface'][interface].update({'is_source_interface' : tmp})

            # Bridge members must not have an assigned address
            tmp = has_address_configured(conf, interface)
            if tmp: bridge['member']['interface'][interface].update({'has_address' : ''})

            # Bridge members must not have a VRF attached
            tmp = has_vrf_configured(conf, interface)
            if tmp: bridge['member']['interface'][interface].update({'has_vrf' : ''})

            # VLAN-aware bridge members must not have VLAN interface configuration
            tmp = has_vlan_subinterface_configured(conf,interface)
            if 'enable_vlan' in bridge and tmp:
                bridge['member']['interface'][interface].update({'has_vlan' : ''})

            # When using VXLAN member interfaces that are configured for Single
            # VXLAN Device (SVD) we need to call the VXLAN conf-mode script to
            # re-create VLAN to VNI mappings if required, but only if the interface
            # is already live on the system - this must not be done on first commit
            if interface.startswith('vxlan') and interface_exists(interface):
                set_dependents('vxlan', conf, interface)
            # When using Wireless member interfaces we need to inform hostapd
            # to properly set-up the bridge
            elif interface.startswith('wlan') and interface_exists(interface):
                set_dependents('wlan', conf, interface)

    # delete empty dictionary keys - no need to run code paths if nothing is there to do
    if 'member' in bridge:
        if 'interface' in bridge['member'] and len(bridge['member']['interface']) == 0:
            del bridge['member']['interface']

        if len(bridge['member']) == 0:
            del bridge['member']

    return bridge

def verify(bridge):
    if 'deleted' in bridge:
        return None

    verify_dhcpv6(bridge)
    verify_vrf(bridge)
    verify_mirror_redirect(bridge)

    ifname = bridge['ifname']

    if dict_search('member.interface', bridge):
        for interface, interface_config in bridge['member']['interface'].items():
            error_msg = f'Can not add interface "{interface}" to bridge, '

            if interface == 'lo':
                raise ConfigError('Loopback interface "lo" can not be added to a bridge')

            if 'is_bridge_member' in interface_config:
                tmp = next(iter(interface_config['is_bridge_member']))
                raise ConfigError(error_msg + f'it is already a member of bridge "{tmp}"!')

            if 'is_bond_member' in interface_config:
                tmp = next(iter(interface_config['is_bond_member']))
                raise ConfigError(error_msg + f'it is already a member of bond "{tmp}"!')

            if 'is_source_interface' in interface_config:
                tmp = interface_config['is_source_interface']
                raise ConfigError(error_msg + f'it is the source-interface of "{tmp}"!')

            if 'has_address' in interface_config:
                raise ConfigError(error_msg + 'it has an address assigned!')

            if 'has_vrf' in interface_config:
                raise ConfigError(error_msg + 'it has a VRF assigned!')

            if 'enable_vlan' in bridge:
                if 'has_vlan' in interface_config:
                    raise ConfigError(error_msg + 'it has VLAN subinterface(s) assigned!')
            else:
                for option in ['allowed_vlan', 'native_vlan']:
                    if option in interface_config:
                        raise ConfigError('Can not use VLAN options on non VLAN aware bridge')

    if 'enable_vlan' in bridge:
        if dict_search('vif.1', bridge):
            raise ConfigError(f'VLAN 1 sub interface cannot be set for VLAN aware bridge {ifname}, and VLAN 1 is always the parent interface')
    else:
        if dict_search('vif', bridge):
            raise ConfigError(f'You must first activate "enable-vlan" of {ifname} bridge to use "vif"')

    return None

def generate(bridge):
    return None

def apply(bridge):
    br = BridgeIf(bridge['ifname'])
    if 'deleted' in bridge:
        # delete interface
        br.remove()
    else:
        br.update(bridge)

    tmp = []
    if 'member' in bridge:
        if 'interface_remove' in bridge['member']:
            tmp.extend(bridge['member']['interface_remove'])
        if 'interface' in bridge['member']:
            tmp.extend(bridge['member']['interface'])

    for interface in tmp:
        if interface.startswith(tuple(['vxlan', 'wlan'])) and interface_exists(interface):
            try:
                call_dependents()
            except ConfigError:
                raise ConfigError('Error updating member interface configuration after changing bridge!')

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
