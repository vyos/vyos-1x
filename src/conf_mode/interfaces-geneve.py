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

from sys import exit
from copy import deepcopy

from vyos.configdict import list_diff
from vyos.config import Config
from vyos.ifconfig import GeneveIf, Interface
from vyos.interfaces import get_type_of_interface
from vyos import ConfigError
from netifaces import interfaces

default_config_data = {
    'address': [],
    'deleted': False,
    'description': '',
    'disable': False,
    'intf': '',
    'ip_arp_cache_tmo': 30,
    'ip_proxy_arp': 0,
    'mtu': 1450,
    'remote': ''
}

def get_config():
    geneve = deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    try:
        geneve['intf'] = os.environ['VYOS_TAGNODE_VALUE']
    except KeyError as E:
        print("Interface not specified")

    # Check if interface has been removed
    if not conf.exists('interfaces geneve ' + geneve['intf']):
        geneve['deleted'] = True
        return geneve

    # set new configuration level
    conf.set_level('interfaces geneve ' + geneve['intf'])

    # retrieve configured interface addresses
    if conf.exists('address'):
        geneve['address'] = conf.return_values('address')

    # retrieve interface description
    if conf.exists('description'):
        geneve['description'] = conf.return_value('description')

    # Disable this interface
    if conf.exists('disable'):
        geneve['disable'] = True

    # ARP cache entry timeout in seconds
    if conf.exists('ip arp-cache-timeout'):
        geneve['ip_arp_cache_tmo'] = int(conf.return_value('ip arp-cache-timeout'))

    # Enable proxy-arp on this interface
    if conf.exists('ip enable-proxy-arp'):
        geneve['ip_proxy_arp'] = 1

    # Maximum Transmission Unit (MTU)
    if conf.exists('mtu'):
        geneve['mtu'] = int(conf.return_value('mtu'))

    # Remote address of GENEVE tunnel
    if conf.exists('remote'):
        geneve['remote'] = conf.return_value('remote')

    # Virtual Network Identifier
    if conf.exists('vni'):
        geneve['vni'] = conf.return_value('vni')

    return geneve


def verify(geneve):
    if geneve['deleted']:
        # bail out early
        return None

    if not geneve['remote']:
        raise ConfigError('GENEVE remote must be configured')

    if not geneve['vni']:
        raise ConfigError('GENEVE VNI must be configured')

    return None


def generate(geneve):
    return None


def apply(geneve):
    # Check if GENEVE interface already exists
    if geneve['intf'] in interfaces():
        v = GeneveIf(geneve['intf'])
        # GENEVE is super picky and the tunnel always needs to be recreated,
        # thus we can simply always delete it first.
        v.remove()

    if not geneve['deleted']:
        # GENEVE interface needs to be created on-block
        # instead of passing a ton of arguments, I just use a dict
        # that is managed by vyos.ifconfig
        conf = deepcopy(GeneveIf.get_config())

        # Assign GENEVE instance configuration parameters to config dict
        conf['vni'] = geneve['vni']
        conf['remote'] = geneve['remote']

        # Finally create the new interface
        v = GeneveIf(geneve['intf'], config=conf)
        # update interface description used e.g. by SNMP
        v.set_alias(geneve['description'])
        # Maximum Transfer Unit (MTU)
        v.set_mtu(geneve['mtu'])

        # configure ARP cache timeout in milliseconds
        v.set_arp_cache_tmo(geneve['ip_arp_cache_tmo'])
        # Enable proxy-arp on this interface
        v.set_proxy_arp(geneve['ip_proxy_arp'])

        # Configure interface address(es) - no need to implicitly delete the
        # old addresses as they have already been removed by deleting the
        # interface above
        for addr in geneve['address']:
            v.add_addr(addr)

        # As the bond interface is always disabled first when changing
        # parameters we will only re-enable the interface if it is not
        # administratively disabled
        if not geneve['disable']:
            v.set_state('up')

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
