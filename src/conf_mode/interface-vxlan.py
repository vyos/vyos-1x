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

from vyos.configdict import list_diff
from vyos.config import Config
from vyos.ifconfig import VXLANIf, Interface
from vyos.interfaces import get_type_of_interface
from vyos import ConfigError
from netifaces import interfaces

default_config_data = {
    'address': [],
    'address_remove': [],
    'deleted': False,
    'description': '',
    'disable': False,
    'group': '',
    'intf': '',
    'ip_arp_cache_tmo': 30,
    'ip_proxy_arp': 0,
    'link': '',
    'mtu': 1450,
    'remote': '',
    'remote_port': 8472 # The Linux implementation of VXLAN pre-dates
                        # the IANA's selection of a standard destination port
}


def get_config():
    vxlan = deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    try:
        vxlan['intf'] = environ['VYOS_TAGNODE_VALUE']
    except KeyError as E:
        print("Interface not specified")

    # Check if interface has been removed
    if not conf.exists('interfaces vxlan ' + vxlan['intf']):
        vxlan['deleted'] = True
        return vxlan

    # set new configuration level
    conf.set_level('interfaces vxlan ' + vxlan['intf'])

    # retrieve configured interface addresses
    if conf.exists('address'):
        vxlan['address'] = conf.return_values('address')

    # Determine interface addresses (currently effective) - to determine which
    # address is no longer valid and needs to be removed from the interface
    eff_addr = conf.return_effective_values('address')
    act_addr = conf.return_values('address')
    vxlan['address_remove'] = list_diff(eff_addr, act_addr)

    # retrieve interface description
    if conf.exists('description'):
        vxlan['description'] = conf.return_value('description')

    # Disable this interface
    if conf.exists('disable'):
        vxlan['disable'] = True

    # VXLAN multicast grou
    if conf.exists('group'):
        vxlan['group'] = conf.return_value('group')

    # ARP cache entry timeout in seconds
    if conf.exists('ip arp-cache-timeout'):
        vxlan['ip_arp_cache_tmo'] = int(conf.return_value('ip arp-cache-timeout'))

    # Enable proxy-arp on this interface
    if conf.exists('ip enable-proxy-arp'):
        vxlan['ip_proxy_arp'] = 1

    # VXLAN underlay interface
    if conf.exists('link'):
        vxlan['link'] = conf.return_value('link')

    # Maximum Transmission Unit (MTU)
    if conf.exists('mtu'):
        vxlan['mtu'] = int(conf.return_value('mtu'))

    # Remote address of VXLAN tunnel
    if conf.exists('remote'):
        vxlan['remote'] = conf.return_value('remote')

    # Remote port of VXLAN tunnel
    if conf.exists('port'):
        vxlan['remote_port'] = int(conf.return_value('port'))

    # Virtual Network Identifier
    if conf.exists('vni'):
        vxlan['vni'] = conf.return_value('vni')

    return vxlan


def verify(vxlan):
    if vxlan['deleted']:
        # bail out early
        return None

    if vxlan['mtu'] < 1500:
        print('WARNING: RFC7348 recommends VXLAN tunnels preserve a 1500 byte MTU')

    if vxlan['group'] and not vxlan['link']:
        raise ConfigError('Multicast VXLAN requires an underlaying interface ')

    if not (vxlan['group'] or vxlan['remote']):
        raise ConfigError('Group or remote must be configured')

    if not vxlan['vni']:
        raise ConfigError('Must configure VNI for VXLAN')

    if vxlan['link']:
        # VXLAN adds a 50 byte overhead - we need to check the underlaying MTU
        # if our configured MTU is at least 50 bytes less
        underlay_mtu = int(Interface(vxlan['link']).mtu)
        if underlay_mtu < (vxlan['mtu'] + 50):
            raise ConfigError('VXLAN has a 50 byte overhead, underlaying device ' \
                              'MTU is to small ({})'.format(underlay_mtu))

    return None


def generate(vxlan):
    return None


def apply(vxlan):
    # Check if the VXLAN interface already exists
    if vxlan['intf'] in interfaces():
        v = VXLANIf(vxlan['intf'])
        # VXLAN is super picky and the tunnel always needs to be recreated,
        # thus we can simply always delete it first.
        v.remove()

    if not vxlan['deleted']:
        # VXLAN interface needs to be created on-block
        # instead of passing a ton of arguments, I just use a dict
        # that is managed by vyos.ifconfig
        conf = deepcopy(VXLANIf.get_config())

        # Assign VXLAN instance configuration parameters to config dict
        conf['vni'] = vxlan['vni']
        conf['group'] = vxlan['group']
        conf['dev'] = vxlan['link']
        conf['remote'] = vxlan['remote']
        conf['port'] = vxlan['remote_port']

        # Finally create the new interface
        v = VXLANIf(vxlan['intf'], config=conf)
        # update interface description used e.g. by SNMP
        v.ifalias = vxlan['description']
        # Maximum Transfer Unit (MTU)
        v.mtu = vxlan['mtu']

        # configure ARP cache timeout in milliseconds
        v.arp_cache_tmp = vxlan['ip_arp_cache_tmo']
        # Enable proxy-arp on this interface
        v.proxy_arp = vxlan['ip_proxy_arp']

        # Configure interface address(es)
        # - not longer required addresses get removed first
        # - newly addresses will be added second
        for addr in vxlan['address_remove']:
            v.del_addr(addr)
        for addr in vxlan['address']:
            v.add_addr(addr)

        # As the bond interface is always disabled first when changing
        # parameters we will only re-enable the interface if it is not
        # administratively disabled
        if not vxlan['disable']:
            v.state='up'

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
