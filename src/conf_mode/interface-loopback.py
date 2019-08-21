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
}

def diff(first, second):
    second = set(second)
    return [item for item in first if item not in second]

def get_config():
    loopback = copy.deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    try:
        loopback['intf'] = os.environ['VYOS_TAGNODE_VALUE']
    except KeyError as E:
        print("Interface not specified")

    # Check if interface has been removed
    if not conf.exists('interfaces loopback ' + loopback['intf']):
        loopback['deleted'] = True

    # set new configuration level
    conf.set_level('interfaces loopback ' + loopback['intf'])

    # retrieve configured interface addresses
    if conf.exists('address'):
        loopback['address'] = conf.return_values('address')

    # retrieve interface description
    if conf.exists('description'):
        loopback['description'] = conf.return_value('description')

    # Determine interface addresses (currently effective) - to determine which
    # address is no longer valid and needs to be removed from the interface
    eff_addr = conf.return_effective_values('address')
    act_addr = conf.return_values('address')
    loopback['address_remove'] = diff(eff_addr, act_addr)

    return loopback

def verify(loopback):
    return None

def generate(loopback):
    return None

def apply(loopback):
    # Remove loopback interface
    if not loopback['deleted']:
        # update interface description used e.g. within SNMP
        VyIfconfig.set_description(loopback['intf'], loopback['description'])

        # Configure interface address(es)
        for addr in loopback['address']:
            VyIfconfig.add_interface_address(loopback['intf'], addr)

    # Remove interface address(es)
    for addr in loopback['address_remove']:
        VyIfconfig.remove_interface_address(loopback['intf'], addr)

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
