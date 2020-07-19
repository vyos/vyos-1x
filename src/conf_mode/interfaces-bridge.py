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
from vyos.configdiff import get_config_diff, Diff
from vyos.configverify import verify_dhcpv6
from vyos.configverify import verify_vrf
from vyos.ifconfig import BridgeIf
from vyos.validate import is_member, has_address_configured
from vyos.xml import defaults

from vyos.util import cmd
from vyos import ConfigError

from vyos import airbag
airbag.enable()

def get_removed_members(conf):
    D = get_config_diff(conf, key_mangling=('-', '_'))
    D.set_level(conf.get_level())
    # get_child_nodes() will return dict_keys(), mangle this into a list with PEP448
    keys = D.get_child_nodes_diff(['member', 'interface'], expand_nodes=Diff.DELETE)['delete'].keys()
    return list(keys)

def get_config():
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    conf = Config()
    base = ['interfaces', 'bridge']

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    ifname = os.environ['VYOS_TAGNODE_VALUE']
    bridge = get_interface_dict(conf, base, ifname)

    # determine which members have been removed
    tmp = get_removed_members(conf)
    if tmp:
        if 'member' in bridge:
            bridge['member'].update({'interface_remove': tmp })
        else:
            bridge.update({'member': {'interface_remove': tmp }})

    if 'member' in bridge and 'interface' in bridge['member']:
        # XXX TT2665 we need a copy of the dict keys for iteration, else we will get:
        # RuntimeError: dictionary changed size during iteration
        for interface in list(bridge['member']['interface']):
            for key in ['cost', 'priority']:
                if interface == key:
                    del bridge['member']['interface'][key]
                    continue

        # the default dictionary is not properly paged into the dict (see T2665)
        # thus we will ammend it ourself
        default_member_values = defaults(base + ['member', 'interface'])

        for interface, interface_config in bridge['member']['interface'].items():
            interface_config.update(default_member_values)

            # Check if we are a member of another bridge device
            tmp = is_member(conf, interface, 'bridge')
            if tmp and tmp != ifname:
                interface_config.update({'is_bridge_member' : tmp})

            # Check if we are a member of a bond device
            tmp = is_member(conf, interface, 'bonding')
            if tmp:
                interface_config.update({'is_bond_member' : tmp})

            # Bridge members must not have an assigned address
            tmp = has_address_configured(conf, interface)
            if tmp:
                interface_config.update({'has_address' : ''})

    return bridge

def verify(bridge):
    if 'deleted' in bridge:
        return None

    verify_dhcpv6(bridge)
    verify_vrf(bridge)

    if 'member' in bridge:
        member = bridge.get('member')
        bridge_name = bridge['ifname']
        for interface, interface_config in member.get('interface', {}).items():
            error_msg = f'Can not add interface "{interface}" to bridge "{bridge_name}", '

            if interface == 'lo':
                raise ConfigError('Loopback interface "lo" can not be added to a bridge')

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
