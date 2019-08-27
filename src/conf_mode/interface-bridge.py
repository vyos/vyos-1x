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
from pyroute2 import IPDB
from netifaces import interfaces
from vyos.config import Config
from vyos import ConfigError

default_config_data = {
    'address': [],
    'address_remove': [],
    'aging': 300,
    'arp_cache_timeout_ms': 30000,
    'description': '',
    'deleted': False,
    'disable': False,
    'disable_link_detect': 1,
    'forwarding_delay': 14,
    'hello_time': 2,
    'igmp_querier': 0,
    'intf': '',
    'mac' : '',
    'max_age': 20,
    'member': [],
    'member_remove': [],
    'priority': 32768,
    'stp': 0
}

def diff(first, second):
    second = set(second)
    return [item for item in first if item not in second]

def get_config():
    bridge = deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    try:
        bridge['intf'] = environ['VYOS_TAGNODE_VALUE']
    except KeyError as E:
        print("Interface not specified")

    # Check if bridge has been removed
    if not conf.exists('interfaces bridge ' + bridge['intf']):
        bridge['deleted'] = True
        return bridge

    # set new configuration level
    conf.set_level('interfaces bridge ' + bridge['intf'])

    # retrieve configured interface addresses
    if conf.exists('address'):
        bridge['address'] = conf.return_values('address')

    # retrieve aging - how long addresses are retained
    if conf.exists('aging'):
        bridge['aging'] = int(conf.return_value('aging'))

    # retrieve interface description
    if conf.exists('description'):
        bridge['description'] = conf.return_value('description')
    else:
        bridge['description'] = bridge['intf']

    # Disable this bridge interface
    if conf.exists('disable'):
        bridge['disable'] = True

    # Ignore link state changes
    if conf.exists('disable-link-detect'):
        bridge['disable_link_detect'] = 2

    # Forwarding delay
    if conf.exists('forwarding-delay'):
        bridge['forwarding_delay'] = int(conf.return_value('forwarding-delay'))

    # Hello packet advertisment interval
    if conf.exists('hello-time'):
        bridge['hello_time'] = int(conf.return_value('hello-time'))

    # Enable Internet Group Management Protocol (IGMP) querier
    if conf.exists('igmp querier'):
        bridge['igmp_querier'] = 1

    # ARP cache entry timeout in seconds
    if conf.exists('ip arp-cache-timeout'):
        bridge['arp_cache_timeout_ms'] = int(conf.return_value('ip arp-cache-timeout')) * 1000

    # Media Access Control (MAC) address
    if conf.exists('mac'):
        bridge['mac'] = conf.return_value('mac')

    # Interval at which neighbor bridges are removed
    if conf.exists('max-age'):
        bridge['max_age'] = int(conf.return_value('max-age'))

    # Determine bridge member interface (currently configured)
    for intf in conf.list_nodes('member interface'):
        # cost and priority initialized with linux defaults
        # by reading /sys/devices/virtual/net/br0/brif/eth2/{path_cost,priority}
        # after adding interface to bridge after reboot
        iface = {
            'name': intf,
            'cost': 100,
            'priority': 32
        }

        if conf.exists('member interface {} cost'.format(intf)):
            iface['cost'] = int(conf.return_value('member interface {} cost'.format(intf)))

        if conf.exists('member interface {} priority'.format(intf)):
            iface['priority'] = int(conf.return_value('member interface {} priority'.format(intf)))

        bridge['member'].append(iface)

    # Determine bridge member interface (currently effective) - to determine which
    # interfaces is no longer assigend to the bridge and thus can be removed
    eff_intf = conf.list_effective_nodes('member interface')
    act_intf = conf.list_nodes('member interface')
    bridge['member_remove'] = diff(eff_intf, act_intf)

    # Determine interface addresses (currently effective) - to determine which
    # address is no longer valid and needs to be removed from the bridge
    eff_addr = conf.return_effective_values('address')
    act_addr = conf.return_values('address')
    bridge['address_remove'] = diff(eff_addr, act_addr)

    # Priority for this bridge
    if conf.exists('priority'):
        bridge['priority'] = int(conf.return_value('priority'))

    # Enable spanning tree protocol
    if conf.exists('stp'):
        bridge['stp'] = 1

    return bridge

def verify(bridge):
    conf = Config()
    for br in conf.list_nodes('interfaces bridge'):
        # it makes no sense to verify ourself in this case
        if br == bridge['intf']:
            continue

        for intf in bridge['member']:
            tmp = conf.list_nodes('interfaces bridge {} member interface'.format(br))
            if intf['name'] in tmp:
                raise ConfigError('Interface "{}" belongs to bridge "{}" and can not be enslaved.'.format(intf['name'], bridge['intf']))

    # the interface must exist prior adding it to a bridge
    for intf in bridge['member']:
        if intf['name'] not in interfaces():
            raise ConfigError('Can not add non existing interface "{}" to bridge "{}"'.format(intf['name'], bridge['intf']))

    return None

def generate(bridge):
    return None

def apply(bridge):
    ipdb = IPDB(mode='explicit')
    brif = bridge['intf']

    if bridge['deleted']:
        try:
            # delete bridge interface
            with ipdb.interfaces[ brif ] as br:
                br.remove()
        except:
            pass
    else:
        try:
            # create bridge interface if it not already exists
            ipdb.create(kind='bridge', ifname=brif).commit()
        except:
            pass

        # get handle in bridge interface
        br = ipdb.interfaces[brif]
        # begin() a transaction prior to make any change
        br.begin()
        # enable interface
        br.up()
        # set ageing time - - value is in centiseconds YES! centiseconds!
        br.br_ageing_time = bridge['aging'] * 100
        # set bridge forward delay - value is in centiseconds YES! centiseconds!
        br.br_forward_delay = bridge['forwarding_delay'] * 100
        # set hello time - value is in centiseconds YES! centiseconds!
        br.br_hello_time = bridge['hello_time'] * 100
        # set max message age - value is in centiseconds YES! centiseconds!
        br.br_max_age = bridge['max_age'] * 100
        # set bridge priority
        br.br_priority = bridge['priority']
        # turn stp on/off
        br.br_stp_state = bridge['stp']
        # enable or disable IGMP querier
        br.br_mcast_querier = bridge['igmp_querier']
        # update interface description used e.g. within SNMP
        br.ifalias = bridge['description']

        # Change interface MAC address
        if bridge['mac']:
            br.set_address = bridge['mac']

        # remove interface from bridge
        for intf in bridge['member_remove']:
            br.del_port( intf['name'] )

        # configure bridge member interfaces
        for member in bridge['member']:
            # add interface
            br.add_port(member['name'])

        # Configure interface address(es)
        for addr in bridge['address_remove']:
            br.del_ip(addr)
        for addr in bridge['address']:
            br.add_ip(addr)

        # up/down interface
        if bridge['disable']:
            br.down()

        # commit changes on bridge interface
        br.commit()

        # configure additional bridge member options
        for member in bridge['member']:
            # configure ARP cache timeout in milliseconds
            with open('/proc/sys/net/ipv4/neigh/' + member['name'] + '/base_reachable_time_ms', 'w') as f:
                f.write(str(bridge['arp_cache_timeout_ms']))
            # ignore link state changes
            with open('/proc/sys/net/ipv4/conf/' + member['name'] + '/link_filter', 'w') as f:
                f.write(str(bridge['disable_link_detect']))

            # adjust member port stp attributes
            member_if = ipdb.interfaces[ member['name'] ]
            member_if.begin()
            # set bridge port cost
            member_if.brport_cost = member['cost']
            # set bridge port priority
            member_if.brport_priority = member['priority']
            member_if.commit()

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
