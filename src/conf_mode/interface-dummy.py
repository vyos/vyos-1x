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

from os import environ
from copy import deepcopy
from sys import exit
from vyos.config import Config
from vyos.ifconfig import DummyIf
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
    dummy = deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    try:
        dummy['intf'] = environ['VYOS_TAGNODE_VALUE']
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
    return None

def generate(dummy):
    return None

def apply(dummy):
    du = DummyIf(dummy['intf'])

    # Remove dummy interface
    if dummy['deleted']:
        du.remove()
    else:
        # enable interface
        du.state = 'up'
        # update interface description used e.g. within SNMP
        du.ifalias = dummy['description']

        # Configure interface address(es)
        for addr in dummy['address_remove']:
            du.del_addr(addr)
        for addr in dummy['address']:
            du.add_addr(addr)

        # disable interface on demand
        if dummy['disable']:
            du.state = 'down'

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
