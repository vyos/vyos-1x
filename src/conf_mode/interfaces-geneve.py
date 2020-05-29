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
from netifaces import interfaces

from vyos.config import Config
from vyos.ifconfig import GeneveIf
from vyos.validate import is_member
from vyos import ConfigError

from vyos import airbag
airbag.enable()

default_config_data = {
    'address': [],
    'deleted': False,
    'description': '',
    'disable': False,
    'intf': '',
    'ip_arp_cache_tmo': 30,
    'ip_proxy_arp': 0,
    'is_bridge_member': False,
    'mtu': 1500,
    'remote': '',
    'vni': ''
}

def get_config():
    geneve = deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    geneve['intf'] = os.environ['VYOS_TAGNODE_VALUE']

    # check if interface is member if a bridge
    geneve['is_bridge_member'] = is_member(conf, geneve['intf'], 'bridge')

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
        if geneve['is_bridge_member']:
            raise ConfigError((
                f'Cannot delete interface "{geneve["intf"]}" as it is a '
                f'member of bridge "{geneve["is_bridge_member"]}"!'))

        return None

    if geneve['is_bridge_member'] and geneve['address']:
        raise ConfigError((
            f'Cannot assign address to interface "{geneve["intf"]}" '
            f'as it is a member of bridge "{geneve["is_bridge_member"]}"!'))

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
        g = GeneveIf(geneve['intf'])
        # GENEVE is super picky and the tunnel always needs to be recreated,
        # thus we can simply always delete it first.
        g.remove()

    if not geneve['deleted']:
        # GENEVE interface needs to be created on-block
        # instead of passing a ton of arguments, I just use a dict
        # that is managed by vyos.ifconfig
        conf = deepcopy(GeneveIf.get_config())

        # Assign GENEVE instance configuration parameters to config dict
        conf['vni'] = geneve['vni']
        conf['remote'] = geneve['remote']

        # Finally create the new interface
        g = GeneveIf(geneve['intf'], **conf)
        # update interface description used e.g. by SNMP
        g.set_alias(geneve['description'])
        # Maximum Transfer Unit (MTU)
        g.set_mtu(geneve['mtu'])

        # configure ARP cache timeout in milliseconds
        g.set_arp_cache_tmo(geneve['ip_arp_cache_tmo'])
        # Enable proxy-arp on this interface
        g.set_proxy_arp(geneve['ip_proxy_arp'])

        # Configure interface address(es) - no need to implicitly delete the
        # old addresses as they have already been removed by deleting the
        # interface above
        for addr in geneve['address']:
            g.add_addr(addr)

        # As the GENEVE interface is always disabled first when changing
        # parameters we will only re-enable the interface if it is not
        # administratively disabled
        if not geneve['disable']:
            g.set_admin_state('up')

        # re-add ourselves to any bridge we might have fallen out of
        if geneve['is_bridge_member']:
            g.add_to_bridge(geneve['is_bridge_member'])

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
