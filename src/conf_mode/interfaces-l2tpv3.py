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
from vyos.ifconfig import L2TPv3If, Interface
from vyos import ConfigError
from vyos.util import call
from vyos.validate import is_bridge_member, is_addr_assigned

default_config_data = {
    'address': [],
    'deleted': False,
    'description': '',
    'disable': False,
    'encapsulation': 'udp',
    'local_address': '',
    'local_port': 5000,
    'intf': '',
    'ipv6_autoconf': 0,
    'ipv6_eui64_prefix': '',
    'ipv6_forwarding': 1,
    'ipv6_dup_addr_detect': 1,
    'is_bridge_member': False,
    'mtu': 1488,
    'peer_session_id': '',
    'peer_tunnel_id': '',
    'remote_address': '',
    'remote_port': 5000,
    'session_id': '',
    'tunnel_id': ''
}

def check_kmod():
    modules = ['l2tp_eth', 'l2tp_netlink', 'l2tp_ip', 'l2tp_ip6']
    for module in modules:
        if not os.path.exists(f'/sys/module/{module}'):
            if call(f'modprobe {module}') != 0:
                raise ConfigError(f'Loading Kernel module {module} failed')

def get_config():
    l2tpv3 = deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    l2tpv3['intf'] = os.environ['VYOS_TAGNODE_VALUE']

    # Check if interface has been removed
    if not conf.exists('interfaces l2tpv3 ' + l2tpv3['intf']):
        l2tpv3['deleted'] = True
        interface = l2tpv3['intf']
        # check if interface is member if a bridge
        l2tpv3['is_bridge_member'] = is_bridge_member(conf, interface)

        # to delete the l2tpv3 interface we need the current tunnel_id and session_id
        if conf.exists_effective(f'interfaces l2tpv3 {interface} tunnel-id'):
            l2tpv3['tunnel_id'] = conf.return_effective_value(f'interfaces l2tpv3 {interface} tunnel-id')

        if conf.exists_effective(f'interfaces l2tpv3 {interface} session-id'):
            l2tpv3['session_id'] = conf.return_effective_value(f'interfaces l2tpv3 {interface} session-id')

        return l2tpv3

    # set new configuration level
    conf.set_level('interfaces l2tpv3 ' + l2tpv3['intf'])

    # retrieve configured interface addresses
    if conf.exists('address'):
        l2tpv3['address'] = conf.return_values('address')

    # retrieve interface description
    if conf.exists('description'):
        l2tpv3['description'] = conf.return_value('description')

    # get tunnel destination port
    if conf.exists('destination-port'):
        l2tpv3['remote_port'] = int(conf.return_value('destination-port'))

    # Disable this interface
    if conf.exists('disable'):
        l2tpv3['disable'] = True

    # get tunnel encapsulation type
    if conf.exists('encapsulation'):
        l2tpv3['encapsulation'] = conf.return_value('encapsulation')

    # get tunnel local ip address
    if conf.exists('local-ip'):
        l2tpv3['local_address'] = conf.return_value('local-ip')

    # Enable acquisition of IPv6 address using stateless autoconfig (SLAAC)
    if conf.exists('ipv6 address autoconf'):
        l2tpv3['ipv6_autoconf'] = 1

    # Get prefix for IPv6 addressing based on MAC address (EUI-64)
    if conf.exists('ipv6 address eui64'):
        l2tpv3['ipv6_eui64_prefix'] = conf.return_value('ipv6 address eui64')

    # Disable IPv6 forwarding on this interface
    if conf.exists('ipv6 disable-forwarding'):
        l2tpv3['ipv6_forwarding'] = 0

    # IPv6 Duplicate Address Detection (DAD) tries
    if conf.exists('ipv6 dup-addr-detect-transmits'):
        l2tpv3['ipv6_dup_addr_detect'] = int(conf.return_value('ipv6 dup-addr-detect-transmits'))

    # Maximum Transmission Unit (MTU)
    if conf.exists('mtu'):
        l2tpv3['mtu'] = int(conf.return_value('mtu'))

    # Remote session id
    if conf.exists('peer-session-id'):
        l2tpv3['peer_session_id'] = conf.return_value('peer-session-id')

    # Remote tunnel id
    if conf.exists('peer-tunnel-id'):
        l2tpv3['peer_tunnel_id'] = conf.return_value('peer-tunnel-id')

    # Remote address of L2TPv3 tunnel
    if conf.exists('remote-ip'):
        l2tpv3['remote_address'] = conf.return_value('remote-ip')

    # Local session id
    if conf.exists('session-id'):
        l2tpv3['session_id'] = conf.return_value('session-id')

    # get local tunnel port
    if conf.exists('source-port'):
        l2tpv3['local_port'] = conf.return_value('source-port')

    # get local tunnel id
    if conf.exists('tunnel-id'):
        l2tpv3['tunnel_id'] = conf.return_value('tunnel-id')

    return l2tpv3


def verify(l2tpv3):
    interface = l2tpv3['intf']

    if l2tpv3['deleted']:
        if l2tpv3['is_bridge_member']:
            interface = l2tpv3['intf']
            bridge = l2tpv3['is_bridge_member']
            raise ConfigError(f'Interface "{interface}" can not be deleted as it belongs to bridge "{bridge}"!')

        return None

    if not l2tpv3['local_address']:
        raise ConfigError(f'Must configure the l2tpv3 local-ip for {interface}')

    if not is_addr_assigned(l2tpv3['local_address']):
        raise ConfigError(f'Must use a configured IP on l2tpv3 local-ip for {interface}')

    if not l2tpv3['remote_address']:
        raise ConfigError(f'Must configure the l2tpv3 remote-ip for {interface}')

    if not l2tpv3['tunnel_id']:
        raise ConfigError(f'Must configure the l2tpv3 tunnel-id for {interface}')

    if not l2tpv3['peer_tunnel_id']:
        raise ConfigError(f'Must configure the l2tpv3 peer-tunnel-id for {interface}')

    if not l2tpv3['session_id']:
        raise ConfigError(f'Must configure the l2tpv3 session-id for {interface}')

    if not l2tpv3['peer_session_id']:
        raise ConfigError(f'Must configure the l2tpv3 peer-session-id for {interface}')

    return None


def generate(l2tpv3):
    return None

def apply(l2tpv3):
    # L2TPv3 interface needs to be created/deleted on-block, instead of
    # passing a ton of arguments, I just use a dict that is managed by
    # vyos.ifconfig
    conf = deepcopy(L2TPv3If.get_config())

    # Check if L2TPv3 interface already exists
    if l2tpv3['intf'] in interfaces():
        # L2TPv3 is picky when changing tunnels/sessions, thus we can simply
        # always delete it first.
        conf['session_id'] = l2tpv3['session_id']
        conf['tunnel_id'] = l2tpv3['tunnel_id']
        l = L2TPv3If(l2tpv3['intf'], **conf)
        l.remove()

    if not l2tpv3['deleted']:
        conf['peer_tunnel_id'] = l2tpv3['peer_tunnel_id']
        conf['local_port'] = l2tpv3['local_port']
        conf['remote_port'] = l2tpv3['remote_port']
        conf['encapsulation'] = l2tpv3['encapsulation']
        conf['local_address'] = l2tpv3['local_address']
        conf['remote_address'] = l2tpv3['remote_address']
        conf['session_id'] = l2tpv3['session_id']
        conf['tunnel_id'] = l2tpv3['tunnel_id']
        conf['peer_session_id'] = l2tpv3['peer_session_id']

        # Finally create the new interface
        l = L2TPv3If(l2tpv3['intf'], **conf)
        # update interface description used e.g. by SNMP
        l.set_alias(l2tpv3['description'])
        # Maximum Transfer Unit (MTU)
        l.set_mtu(l2tpv3['mtu'])
        # IPv6 address autoconfiguration
        l.set_ipv6_autoconf(l2tpv3['ipv6_autoconf'])
        # IPv6 EUI-based address
        l.set_ipv6_eui64_address(l2tpv3['ipv6_eui64_prefix'])
        # IPv6 forwarding
        l.set_ipv6_forwarding(l2tpv3['ipv6_forwarding'])
        # IPv6 Duplicate Address Detection (DAD) tries
        l.set_ipv6_dad_messages(l2tpv3['ipv6_dup_addr_detect'])

        # Configure interface address(es) - no need to implicitly delete the
        # old addresses as they have already been removed by deleting the
        # interface above
        for addr in l2tpv3['address']:
            l.add_addr(addr)

        # As the interface is always disabled first when changing parameters
        # we will only re-enable the interface if it is not  administratively
        # disabled
        if not l2tpv3['disable']:
            l.set_admin_state('up')

    return None

if __name__ == '__main__':
    try:
        check_kmod()
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
