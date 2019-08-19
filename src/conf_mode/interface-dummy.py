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
#
#

import os
import sys
import copy

import vyos.configinterface as VyIfconfig

from vyos.config import Config
from vyos import ConfigError

default_config_data = {
    'address': [],
    'address_remove': [],
    'deleted': False,
    'description': '',
    'disable': False,
    'intf': ''
}

def diff(first, second):
    second = set(second)
    return [item for item in first if item not in second]

def get_config():
    dummy = copy.deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    try:
        dummy['intf'] = os.environ['VYOS_TAGNODE_VALUE']
    except KeyError as E:
        print("Interface not specified")

    # Check if interface has been removed
    if not conf.exists('interfaces dummy ' + dummy['intf']):
        dummy['deleted'] = True
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
    dummy['address_remove'] = diff(eff_addr, act_addr)

    return dummy

def verify(dummy):
    if dummy is None:
        return None

    return None

def generate(dummy):
    if dummy is None:
        return None

    return None

def apply(dummy):
    if dummy is None:
        return None

    # Remove dummy interface
    if dummy['deleted']:
        VyIfconfig.remove_interface(dummy['intf'])
    else:
        # Interface will only be added if it yet does not exist
        VyIfconfig.add_interface('dummy', dummy['intf'])

        # update interface description used e.g. within SNMP
        VyIfconfig.set_description(dummy['intf'], dummy['description'])

        # Configure interface address(es)
        for addr in dummy['address_remove']:
            VyIfconfig.remove_interface_address(dummy['intf'], addr)

        for addr in dummy['address']:
            VyIfconfig.add_interface_address(dummy['intf'], addr)

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
