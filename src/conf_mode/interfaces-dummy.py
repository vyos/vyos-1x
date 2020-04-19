#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
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

from copy import deepcopy
from sys import exit
from netifaces import interfaces

from vyos.ifconfig import DummyIf
from vyos.configdict import list_diff
from vyos.config import Config
from vyos.validate import is_bridge_member
from vyos import ConfigError

default_config_data = {
    'address': [],
    'address_remove': [],
    'deleted': False,
    'description': '',
    'disable': False,
    'intf': '',
    'is_bridge_member': False,
    'vrf': ''
}

def get_config():
    dummy = deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    dummy['intf'] = os.environ['VYOS_TAGNODE_VALUE']

    # Check if interface has been removed
    if not conf.exists('interfaces dummy ' + dummy['intf']):
        dummy['deleted'] = True
        # check if interface is member if a bridge
        dummy['is_bridge_member'] = is_bridge_member(conf, dummy['intf'])
        return dummy

    # set new configuration level
    conf.set_level('interfaces dummy ' + dummy['intf'])

    # retrieve configured interface addresses
    if conf.exists('address'):
        dummy['address'] = conf.return_values('address')

    # retrieve interface description
    if conf.exists('description'):
        dummy['description'] = conf.return_value('description')

    # Disable this interface
    if conf.exists('disable'):
        dummy['disable'] = True

    # Determine interface addresses (currently effective) - to determine which
    # address is no longer valid and needs to be removed from the interface
    eff_addr = conf.return_effective_values('address')
    act_addr = conf.return_values('address')
    dummy['address_remove'] = list_diff(eff_addr, act_addr)

    # retrieve VRF instance
    if conf.exists('vrf'):
        dummy['vrf'] = conf.return_value('vrf')

    return dummy

def verify(dummy):
    if dummy['deleted']:
        if dummy['is_bridge_member']::
            interface = dummy['intf']
            bridge = dummy['is_bridge_member']
            raise ConfigError(f'Interface "{interface}" can not be deleted as it belongs to bridge "{bridge}"!')

        return None

    vrf_name = dummy['vrf']
    if vrf_name and vrf_name not in interfaces():
        raise ConfigError(f'VRF "{vrf_name}" does not exist')

    return None

def generate(dummy):
    return None

def apply(dummy):
    d = DummyIf(dummy['intf'])

    # Remove dummy interface
    if dummy['deleted']:
        d.remove()
    else:
        # update interface description used e.g. within SNMP
        d.set_alias(dummy['description'])

        # Configure interface address(es)
        # - not longer required addresses get removed first
        # - newly addresses will be added second
        for addr in dummy['address_remove']:
            d.del_addr(addr)
        for addr in dummy['address']:
            d.add_addr(addr)

        # assign/remove VRF
        d.set_vrf(dummy['vrf'])

        # disable interface on demand
        if dummy['disable']:
            d.set_admin_state('down')
        else:
            d.set_admin_state('up')

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
