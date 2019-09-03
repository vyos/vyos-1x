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

from copy import deepcopy
from sys import exit
from netifaces import interfaces
from vyos.ifconfig import BondIf
from vyos.config import Config
from vyos import ConfigError

default_config_data = {
    'address': [],
    'address_remove': [],
    'arp_mon_intvl': 0,
    'arp_mon_tgt': [],
    'description': '',
    'deleted': False,
    'dhcp_client_id': '',
    'dhcp_hostname': '',
    'dhcpv6_prm_only': False,
    'dhcpv6_temporary': False,
    'disable': False,
    'disable_link_detect': 1,
    'hash_policy': 'layer2',
    'ip_arp_cache_tmo': 30,
    'ip_proxy_arp': 0,
    'ip_proxy_arp_pvlan': 0,
    'intf': '',
    'mac': '',
    'mode': '802.3ad',
    'member': [],
    'mtu': 1500,
    'primary': '',
    'vif_s': [],
    'vif': []
}

def diff(first, second):
    second = set(second)
    return [item for item in first if item not in second]

def get_bond_mode(mode):
    if mode == 'round-robin':
        return 'balance-rr'
    elif mode == 'active-backup':
        return 'active-backup'
    elif mode == 'xor-hash':
        return 'balance-xor'
    elif mode == 'broadcast':
        return 'broadcast'
    elif mode == '802.3ad':
        return '802.3ad'
    elif mode == 'transmit-load-balance':
        return 'balance-tlb'
    elif mode == 'adaptive-load-balance':
        return 'balance-alb'
    else:
        raise ConfigError('invalid bond mode "{}"'.format(mode))

def vlan_to_dict(conf):
    """
    Common used function which will extract VLAN related information from config
    and represent the result as Python dictionary.

    Function call's itself recursively if a vif-s/vif-c pair is detected.
    """
    vlan = {
        'id': conf.get_level().split(' ')[-1], # get the '100' in 'interfaces bonding bond0 vif-s 100'
        'address': [],
        'address_remove': [],
        'description': '',
        'dhcp_client_id': '',
        'dhcp_hostname': '',
        'dhcpv6_prm_only': False,
        'dhcpv6_temporary': False,
        'disable': False,
        'disable_link_detect': 1,
        'mac': '',
        'mtu': 1500
    }
    # retrieve configured interface addresses
    if conf.exists('address'):
        vlan['address'] = conf.return_values('address')

    # Determine interface addresses (currently effective) - to determine which
    # address is no longer valid and needs to be removed from the bond
    eff_addr = conf.return_effective_values('address')
    act_addr = conf.return_values('address')
    vlan['address_remove'] = diff(eff_addr, act_addr)

    # retrieve interface description
    if conf.exists('description'):
        vlan['description'] = conf.return_value('description')

    # get DHCP client identifier
    if conf.exists('dhcp-options client-id'):
        vlan['dhcp_client_id'] = conf.return_value('dhcp-options client-id')

    # DHCP client host name (overrides the system host name)
    if conf.exists('dhcp-options host-name'):
        vlan['dhcp_hostname'] = conf.return_value('dhcp-options host-name')

    # DHCPv6 only acquire config parameters, no address
    if conf.exists('dhcpv6-options parameters-only'):
        vlan['dhcpv6_prm_only'] = conf.return_value('dhcpv6-options parameters-only')

    # DHCPv6 temporary IPv6 address
    if conf.exists('dhcpv6-options temporary'):
        vlan['dhcpv6_temporary'] = conf.return_value('dhcpv6-options temporary')

    # ignore link state changes
    if conf.exists('disable-link-detect'):
        vlan['disable_link_detect'] = 2

    # disable bond interface
    if conf.exists('disable'):
        vlan['disable'] = True

    # ethertype (only on vif-s nodes)
    if conf.exists('ethertype'):
        vlan['ethertype'] = conf.return_value('ethertype')

    # Media Access Control (MAC) address
    if conf.exists('mac'):
        vlan['mac'] = conf.return_value('mac')

    # Maximum Transmission Unit (MTU)
    if conf.exists('mtu'):
        vlan['mtu'] = int(conf.return_value('mtu'))

    # check if there is a Q-in-Q vlan customer interface
    # and call this function recursively
    if conf.exists('vif-c'):
        cfg_level = conf.get_level()
        # add new key (vif-c) to dictionary
        vlan['vif-c'] = []
        for vif in conf.list_nodes('vif-c'):
            # set config level to vif interface
            conf.set_level(cfg_level + ' vif-c ' + vif)
            vlan['vif-c'].append(vlan_to_dict(conf))

    return vlan

def get_config():
    # initialize kernel module if not loaded
    if not os.path.isfile('/sys/class/net/bonding_masters'):
        import syslog
        syslog.syslog(syslog.LOG_NOTICE, "loading bonding kernel module")
        if os.system('modprobe bonding max_bonds=0 miimon=250') != 0:
            syslog.syslog(syslog.LOG_NOTICE, "failed loading bonding kernel module")
            raise ConfigError("failed loading bonding kernel module")

    bond = deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    try:
        bond['intf'] = os.environ['VYOS_TAGNODE_VALUE']
    except KeyError as E:
        print("Interface not specified")

    # check if bond has been removed
    cfg_base = 'interfaces bonding ' + bond['intf']
    if not conf.exists(cfg_base):
        bond['deleted'] = True
        return bond

    # set new configuration level
    conf.set_level(cfg_base)

    # retrieve configured interface addresses
    if conf.exists('address'):
        bond['address'] = conf.return_values('address')

    # ARP link monitoring frequency in milliseconds
    if conf.exists('arp-monitor interval'):
        bond['arp_mon_intvl'] = conf.return_value('arp-monitor interval')

    # IP address to use for ARP monitoring
    if conf.exists('arp-monitor target'):
        bond['arp_mon_tgt'] = conf.return_values('arp-monitor target')

    # retrieve interface description
    if conf.exists('description'):
        bond['description'] = conf.return_value('description')
    else:
        bond['description'] = bond['intf']

    # get DHCP client identifier
    if conf.exists('dhcp-options client-id'):
        bond['dhcp_client_id'] = conf.return_value('dhcp-options client-id')

    # DHCP client host name (overrides the system host name)
    if conf.exists('dhcp-options host-name'):
        bond['dhcp_hostname'] = conf.return_value('dhcp-options host-name')

    # DHCPv6 only acquire config parameters, no address
    if conf.exists('dhcpv6-options parameters-only'):
        bond['dhcpv6_prm_only'] = conf.return_value('dhcpv6-options parameters-only')

    # DHCPv6 temporary IPv6 address
    if conf.exists('dhcpv6-options temporary'):
        bond['dhcpv6_temporary'] = conf.return_value('dhcpv6-options temporary')

    # ignore link state changes
    if conf.exists('disable-link-detect'):
        bond['disable_link_detect'] = 2

    # disable bond interface
    if conf.exists('disable'):
        bond['disable'] = True

    # Bonding transmit hash policy
    if conf.exists('hash-policy'):
        bond['hash_policy'] = conf.return_value('hash-policy')

    # ARP cache entry timeout in seconds
    if conf.exists('ip arp-cache-timeout'):
        bond['ip_arp_cache_tmo'] = int(conf.return_value('ip arp-cache-timeout'))

    # Enable proxy-arp on this interface
    if conf.exists('ip enable-proxy-arp'):
        bond['ip_proxy_arp'] = 1

    # Enable private VLAN proxy ARP on this interface
    if conf.exists('ip proxy-arp-pvlan'):
        bond['ip_proxy_arp_pvlan'] = 1

    # Media Access Control (MAC) address
    if conf.exists('mac'):
        bond['mac'] = conf.return_value('mac')

    # Bonding mode
    if conf.exists('mode'):
        bond['mode'] = get_bond_mode(conf.return_value('mode'))

    # Maximum Transmission Unit (MTU)
    if conf.exists('mtu'):
        bond['mtu'] = int(conf.return_value('mtu'))

    # determine bond member interfaces (currently configured)
    if conf.exists('member interface'):
        bond['member'] = conf.return_values('member interface')

    # Determine interface addresses (currently effective) - to determine which
    # address is no longer valid and needs to be removed from the bond
    eff_addr = conf.return_effective_values('address')
    act_addr = conf.return_values('address')
    bond['address_remove'] = diff(eff_addr, act_addr)

    # Primary device interface
    if conf.exists('primary'):
        bond['primary'] = conf.return_value('primary')

    # re-set configuration level and retrieve vif-s interfaces
    conf.set_level(cfg_base)
    if conf.exists('vif-s'):
        for vif_s in conf.list_nodes('vif-s'):
            # set config level to vif-s interface
            conf.set_level(cfg_base + ' vif-s ' + vif_s)
            bond['vif_s'].append(vlan_to_dict(conf))

    # re-set configuration level and retrieve vif-s interfaces
    conf.set_level(cfg_base)
    if conf.exists('vif'):
        for vif in conf.list_nodes('vif'):
            # set config level to vif interface
            conf.set_level(cfg_base + ' vif ' + vif)
            bond['vif'].append(vlan_to_dict(conf))

    return bond

def verify(bond):
    if len (bond['arp_mon_tgt']) > 16:
        raise ConfigError('The maximum number of targets that can be specified is 16')

    if bond['primary']:
        if bond['mode'] not in ['active-backup', 'balance-tlb', 'balance-alb']:
            raise ConfigError('Mode dependency failed, primary not supported in this mode.'.format())

        if bond['primary'] not in bond['member']:
            raise ConfigError('Interface "{}" is not part of the bond'.format(bond['primary']))

    return None

def generate(bond):
    return None

def apply(bond):
    b = BondIf(bond['intf'])

    if bond['deleted']:
        # delete bonding interface
        b.remove()
    else:
        # Some parameters can not be changed when the bond is up.
        # Always disable the bond prior changing anything
        b.state = 'down'

        # Configure interface address(es)
        for addr in bond['address_remove']:
            b.del_addr(addr)
        for addr in bond['address']:
            b.add_addr(addr)

        # ARP link monitoring frequency
        b.arp_interval = bond['arp_mon_intvl']
        # reset miimon on arp-montior deletion
        if bond['arp_mon_intvl'] == 0:
            # reset miimon to default
            b.bond_miimon = 250

        # ARP monitor targets need to be synchronized between sysfs and CLI.
        # Unfortunately an address can't be send twice to sysfs as this will
        # result in the following exception:  OSError: [Errno 22] Invalid argument.
        #
        # We remove ALL adresses prior adding new ones, this will remove addresses
        # added manually by the user too - but as we are limited to 16 adresses
        # from the kernel side this looks valid to me. We won't run into an error
        # when a user added manual adresses which would result in having more
        # then 16 adresses in total.
        cur_addr = list(map(str, b.arp_ip_target.split()))
        for addr in cur_addr:
            b.arp_ip_target = '-' + addr

        # Add configured ARP target addresses
        for addr in bond['arp_mon_tgt']:
            b.arp_ip_target = '+' + addr

        # update interface description used e.g. within SNMP
        b.ifalias = bond['description']

        #
        # missing DHCP/DHCPv6 options go here
        #

        # ignore link state changes
        b.link_detect = bond['disable_link_detect']
        # Bonding transmit hash policy
        b.xmit_hash_policy = bond['hash_policy']
        # configure ARP cache timeout in milliseconds
        b.arp_cache_tmp = bond['ip_arp_cache_tmo']
        # Enable proxy-arp on this interface
        b.proxy_arp = bond['ip_proxy_arp']
        # Enable private VLAN proxy ARP on this interface
        b.proxy_arp_pvlan = bond['ip_proxy_arp_pvlan']

        # Change interface MAC address
        if bond['mac']:
            b.mac = bond['mac']

        # The bonding mode can not be changed when there are interfaces enslaved
        # to this bond, thus we will free all interfaces from the bond first!
        for intf in b.get_slaves():
            b.del_port(intf)

        # Bonding policy
        b.mode = bond['mode']
        # Maximum Transmission Unit (MTU)
        b.mtu = bond['mtu']
        # Primary device interface
        b.primary = bond['primary']

        #
        # VLAN config goes here
        #

        # Add (enslave) interfaces to bond
        for intf in bond['member']:
                b.add_port(intf)

        # As the bond interface is always disabled first when changing
        # parameters we will only re-enable the interface if it is not
        # administratively disabled
        if not bond['disable']:
            b.state = 'up'

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
