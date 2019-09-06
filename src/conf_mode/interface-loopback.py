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

from os import environ
from sys import exit
from copy import deepcopy

from vyos.ifconfig import LoopbackIf
from vyos.configdict import list_diff
from vyos.config import Config
from vyos import ConfigError

default_config_data = {
    'address': [],
    'address_remove': [],
    'deleted': False,
    'description': '',
}


def get_config():
    loopback = deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    try:
        loopback['intf'] = environ['VYOS_TAGNODE_VALUE']
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
    loopback['address_remove'] = list_diff(eff_addr, act_addr)

    return loopback

def verify(loopback):
    return None

def generate(loopback):
    return None

def apply(loopback):
    lo = LoopbackIf(loopback['intf'])
    if not loopback['deleted']:
        # update interface description used e.g. within SNMP
        # update interface description used e.g. within SNMP
        lo.ifalias = loopback['description']

        # Configure interface address(es)
        # - not longer required addresses get removed first
        # - newly addresses will be added second
        for addr in loopback['address']:
            lo.add_addr(addr)

    # remove interface address(es)
    for addr in loopback['address_remove']:
        lo.del_addr(addr)

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
