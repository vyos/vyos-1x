#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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

import os

from sys import exit
from netifaces import interfaces

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configdict import leaf_node_changed
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_dhcpv6
from vyos.configverify import verify_source_interface
from vyos.configverify import verify_vlan_config
from vyos.configverify import verify_vrf
from vyos.ifconfig import BondIf
from vyos.validate import is_member
from vyos.validate import has_address_configured
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_bond_mode(mode):
    if mode == 'round-robin':
        return 'balance-rr'
    elif mode == 'active-backup':
        return 'active-backup'
    elif mode == 'xor-hash':
        return 'balance-xor'
    elif mode == 'broadcast':
        return 'broadcast'
    elif mode == '802.3ad':
        return '802.3ad'
    elif mode == 'transmit-load-balance':
        return 'balance-tlb'
    elif mode == 'adaptive-load-balance':
        return 'balance-alb'
    else:
        raise ConfigError(f'invalid bond mode "{mode}"')

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'bonding']
    bond = get_interface_dict(conf, base)

    # To make our own life easier transfor the list of member interfaces
    # into a dictionary - we will use this to add additional information
    # later on for wach member
    if 'member' in bond and 'interface' in bond['member']:
        # first convert it to a list if only one member is given
        if isinstance(bond['member']['interface'], str):
            bond['member']['interface'] = [bond['member']['interface']]

        tmp={}
        for interface in bond['member']['interface']:
            tmp.update({interface: {}})

        bond['member']['interface'] = tmp

    if 'mode' in bond:
        bond['mode'] = get_bond_mode(bond['mode'])

    tmp = leaf_node_changed(conf, ['mode'])
    if tmp:
        bond.update({'shutdown_required': ''})

    # determine which members have been removed
    tmp = leaf_node_changed(conf, ['member', 'interface'])
    if tmp:
        bond.update({'shutdown_required': ''})
        if 'member' in bond:
            bond['member'].update({'interface_remove': tmp })
        else:
            bond.update({'member': {'interface_remove': tmp }})

    if 'member' in bond and 'interface' in bond['member']:
        for interface, interface_config in bond['member']['interface'].items():
            # Check if we are a member of another bond device
            tmp = is_member(conf, interface, 'bridge')
            if tmp:
                interface_config.update({'is_bridge_member' : tmp})

            # Check if we are a member of a bond device
            tmp = is_member(conf, interface, 'bonding')
            if tmp and tmp != bond['ifname']:
                interface_config.update({'is_bond_member' : tmp})

            # bond members must not have an assigned address
            tmp = has_address_configured(conf, interface)
            if tmp:
                interface_config.update({'has_address' : ''})

    return bond


def verify(bond):
    if 'deleted' in bond:
        verify_bridge_delete(bond)
        return None

    if 'arp_monitor' in bond:
        if 'target' in bond['arp_monitor'] and len(int(bond['arp_monitor']['target'])) > 16:
            raise ConfigError('The maximum number of arp-monitor targets is 16')

        if 'interval' in bond['arp_monitor'] and len(int(bond['arp_monitor']['interval'])) > 0:
            if bond['mode'] in ['802.3ad', 'balance-tlb', 'balance-alb']:
                raise ConfigError('ARP link monitoring does not work for mode 802.3ad, ' \
                                  'transmit-load-balance or adaptive-load-balance')

    if 'primary' in bond:
        if bond['mode'] not in ['active-backup', 'balance-tlb', 'balance-alb']:
            raise ConfigError('Option primary - mode dependency failed, not'
                              'supported in mode {mode}!'.format(**bond))

    verify_address(bond)
    verify_dhcpv6(bond)
    verify_vrf(bond)

    # use common function to verify VLAN configuration
    verify_vlan_config(bond)

    bond_name = bond['ifname']
    if 'member' in bond:
        member = bond.get('member')
        for interface, interface_config in member.get('interface', {}).items():
            error_msg = f'Can not add interface "{interface}" to bond "{bond_name}", '

            if interface == 'lo':
                raise ConfigError('Loopback interface "lo" can not be added to a bond')

            if interface not in interfaces():
                raise ConfigError(error_msg + 'it does not exist!')

            if 'is_bridge_member' in interface_config:
                tmp = interface_config['is_bridge_member']
                raise ConfigError(error_msg + f'it is already a member of bridge "{tmp}"!')

            if 'is_bond_member' in interface_config:
                tmp = interface_config['is_bond_member']
                raise ConfigError(error_msg + f'it is already a member of bond "{tmp}"!')

            if 'has_address' in interface_config:
                raise ConfigError(error_msg + 'it has an address assigned!')


    if 'primary' in bond:
        if bond['primary'] not in bond['member']['interface']:
            raise ConfigError(f'Primary interface of bond "{bond_name}" must be a member interface')

        if bond['mode'] not in ['active-backup', 'balance-tlb', 'balance-alb']:
            raise ConfigError('primary interface only works for mode active-backup, ' \
                              'transmit-load-balance or adaptive-load-balance')

    return None

def generate(bond):
    return None

def apply(bond):
    b = BondIf(bond['ifname'])

    if 'deleted' in bond:
        # delete interface
        b.remove()
    else:
        b.update(bond)

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
