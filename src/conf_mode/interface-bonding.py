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

from copy import deepcopy
from sys import exit
from netifaces import interfaces

from vyos.ifconfig import BondIf, VLANIf
from vyos.configdict import list_diff, vlan_to_dict
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
    'dhcp_vendor_class_id': '',
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
    'vif_s_remove': [],
    'vif': [],
    'vif_remove': []
}


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


def apply_vlan_config(vlan, config):
    """
    Generic function to apply a VLAN configuration from a dictionary
    to a VLAN interface
    """

    if type(vlan) != type(VLANIf("lo")):
        raise TypeError()

    # update interface description used e.g. within SNMP
    vlan.set_alias(config['description'])
    # ignore link state changes
    vlan.set_link_detect(config['disable_link_detect'])
    # Maximum Transmission Unit (MTU)
    vlan.set_mtu(config['mtu'])
    # Change VLAN interface MAC address
    if config['mac']:
        vlan.set_mac(config['mac'])

    # enable/disable VLAN interface
    if config['disable']:
        vlan.set_state('down')
    else:
        vlan.set_state('up')

    # Configure interface address(es)
    # - not longer required addresses get removed first
    # - newly addresses will be added second
    for addr in config['address_remove']:
        vlan.del_addr(addr)
    for addr in config['address']:
        vlan.add_addr(addr)


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

    # get interface addresses (currently effective) - to determine which
    # address is no longer valid and needs to be removed
    eff_addr = conf.return_effective_values('address')
    bond['address_remove'] = list_diff(eff_addr, bond['address'])

    # ARP link monitoring frequency in milliseconds
    if conf.exists('arp-monitor interval'):
        bond['arp_mon_intvl'] = int(conf.return_value('arp-monitor interval'))

    # IP address to use for ARP monitoring
    if conf.exists('arp-monitor target'):
        bond['arp_mon_tgt'] = conf.return_values('arp-monitor target')

    # retrieve interface description
    if conf.exists('description'):
        bond['description'] = conf.return_value('description')

    # get DHCP client identifier
    if conf.exists('dhcp-options client-id'):
        bond['dhcp_client_id'] = conf.return_value('dhcp-options client-id')

    # DHCP client host name (overrides the system host name)
    if conf.exists('dhcp-options host-name'):
        bond['dhcp_hostname'] = conf.return_value('dhcp-options host-name')

    # DHCP client vendor identifier
    if conf.exists('dhcp-options vendor-class-id'):
        bond['dhcp_vendor_class_id'] = conf.return_value('dhcp-options vendor-class-id')

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

    # Primary device interface
    if conf.exists('primary'):
        bond['primary'] = conf.return_value('primary')

    # re-set configuration level to parse new nodes
    conf.set_level(cfg_base)
    # get vif-s interfaces (currently effective) - to determine which vif-s
    # interface is no longer present and needs to be removed
    eff_intf = conf.list_effective_nodes('vif-s')
    act_intf = conf.list_nodes('vif-s')
    bond['vif_s_remove'] = list_diff(eff_intf, act_intf)

    if conf.exists('vif-s'):
        for vif_s in conf.list_nodes('vif-s'):
            # set config level to vif-s interface
            conf.set_level(cfg_base + ' vif-s ' + vif_s)
            bond['vif_s'].append(vlan_to_dict(conf))

    # re-set configuration level to parse new nodes
    conf.set_level(cfg_base)
    # Determine vif interfaces (currently effective) - to determine which
    # vif interface is no longer present and needs to be removed
    eff_intf = conf.list_effective_nodes('vif')
    act_intf = conf.list_nodes('vif')
    bond['vif_remove'] = list_diff(eff_intf, act_intf)

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
            raise ConfigError('Mode dependency failed, primary not supported ' \
                              'in this mode.'.format())

        if bond['primary'] not in bond['member']:
            raise ConfigError('Interface "{}" is not part of the bond' \
                              .format(bond['primary']))

    for vif_s in bond['vif_s']:
        for vif in bond['vif']:
            if vif['id'] == vif_s['id']:
                raise ConfigError('Can not use identical ID on vif and vif-s interface')


    conf = Config()
    for intf in bond['member']:
        # a bonding member interface is only allowed to be assigned to one bond!
        all_bonds = conf.list_nodes('interfaces bonding')
        # We do not need to check our own bond
        all_bonds.remove(bond['intf'])
        for tmp in all_bonds:
            if conf.exists('interfaces bonding ' + tmp + ' member interface ' + intf):
                raise ConfigError('can not enslave interface {} which already ' \
                                  'belongs to {}'.format(intf, tmp))

        # can not add interfaces with an assigned address to a bond
        if conf.exists('interfaces ethernet ' + intf + ' address'):
            raise ConfigError('can not enslave interface {} which has an address ' \
                              'assigned'.format(intf))

        # bond members are not allowed to be bridge members, too
        for tmp in conf.list_nodes('interfaces bridge'):
            if conf.exists('interfaces bridge ' + tmp + ' member interface ' + intf):
                raise ConfigError('can not enslave interface {} which belongs to ' \
                                  'bridge {}'.format(intf, tmp))

        # bond members are not allowed to be vrrp members, too
        for tmp in conf.list_nodes('high-availability vrrp group'):
            if conf.exists('high-availability vrrp group ' + tmp + ' interface ' + intf):
                raise ConfigError('can not enslave interface {} which belongs to ' \
                                  'VRRP group {}'.format(intf, tmp))

        # bond members are not allowed to be underlaying psuedo-ethernet devices
        for tmp in conf.list_nodes('interfaces pseudo-ethernet'):
            if conf.exists('interfaces pseudo-ethernet ' + tmp + ' link ' + intf):
                raise ConfigError('can not enslave interface {} which belongs to ' \
                                  'pseudo-ethernet {}'.format(intf, tmp))

        # bond members are not allowed to be underlaying vxlan devices
        for tmp in conf.list_nodes('interfaces vxlan'):
            if conf.exists('interfaces vxlan ' + tmp + ' link ' + intf):
                raise ConfigError('can not enslave interface {} which belongs to ' \
                                  'vxlan {}'.format(intf, tmp))


    if bond['primary']:
        if bond['primary'] not in bond['member']:
            raise ConfigError('primary interface must be a member interface of {}' \
                              .format(bond['intf']))

        if bond['mode'] not in ['active-backup', 'balance-tlb', 'balance-alb']:
            raise ConfigError('primary interface only works for mode active-backup, ' \
                              'transmit-load-balance or adaptive-load-balance')

    if bond['arp_mon_intvl'] > 0:
        if bond['mode'] in ['802.3ad', 'balance-tlb', 'balance-alb']:
            raise ConfigError('ARP link monitoring does not work for mode 802.3ad, ' \
                              'transmit-load-balance or adaptive-load-balance')

    return None


def generate(bond):
    return None


def apply(bond):
    b = BondIf(bond['intf'])

    if bond['deleted']:
        # delete interface
        b.remove()
    else:
        # Some parameters can not be changed when the bond is up.
        # Always disable the bond prior changing anything
        b.set_state('down')

        # The bonding mode can not be changed when there are interfaces enslaved
        # to this bond, thus we will free all interfaces from the bond first!
        for intf in b.get_slaves():
            b.del_port(intf)

        # ARP link monitoring frequency, reset miimon when arp-montior is inactive
        # this is done inside BondIf automatically
        b.set_arp_interval(bond['arp_mon_intvl'])

        # ARP monitor targets need to be synchronized between sysfs and CLI.
        # Unfortunately an address can't be send twice to sysfs as this will
        # result in the following exception:  OSError: [Errno 22] Invalid argument.
        #
        # We remove ALL adresses prior adding new ones, this will remove addresses
        # added manually by the user too - but as we are limited to 16 adresses
        # from the kernel side this looks valid to me. We won't run into an error
        # when a user added manual adresses which would result in having more
        # then 16 adresses in total.
        arp_tgt_addr = list(map(str, b.get_arp_ip_target().split()))
        for addr in arp_tgt_addr:
            b.set_arp_ip_target('-' + addr)

        # Add configured ARP target addresses
        for addr in bond['arp_mon_tgt']:
            b.set_arp_ip_target('+' + addr)

        # update interface description used e.g. within SNMP
        b.set_alias(bond['description'])

        # get DHCP config dictionary and update values
        opt = b.get_dhcp_options()

        if bond['dhcp_client_id']:
            opt['client_id'] = bond['dhcp_client_id']

        if bond['dhcp_hostname']:
            opt['hostname'] = bond['dhcp_hostname']

        if bond['dhcp_vendor_class_id']:
            opt['vendor_class_id'] = bond['dhcp_vendor_class_id']

        # store DHCP config dictionary - used later on when addresses
        # are requested
        b.set_dhcp_options(opt)

        # ignore link state changes
        b.set_link_detect(bond['disable_link_detect'])
        # Bonding transmit hash policy
        b.set_hash_policy(bond['hash_policy'])
        # configure ARP cache timeout in milliseconds
        b.set_arp_cache_tmo(bond['ip_arp_cache_tmo'])
        # Enable proxy-arp on this interface
        b.set_proxy_arp(bond['ip_proxy_arp'])
        # Enable private VLAN proxy ARP on this interface
        b.set_proxy_arp_pvlan(bond['ip_proxy_arp_pvlan'])

        # Change interface MAC address
        if bond['mac']:
            b.set_mac(bond['mac'])

        # Bonding policy
        b.set_mode(bond['mode'])
        # Maximum Transmission Unit (MTU)
        b.set_mtu(bond['mtu'])

        # Primary device interface
        if bond['primary']:
            b.set_primary(bond['primary'])

        # Add (enslave) interfaces to bond
        for intf in bond['member']:
            b.add_port(intf)

        # As the bond interface is always disabled first when changing
        # parameters we will only re-enable the interface if it is not
        # administratively disabled
        if not bond['disable']:
            b.set_state('up')

        # Configure interface address(es)
        # - not longer required addresses get removed first
        # - newly addresses will be added second
        for addr in bond['address_remove']:
            b.del_addr(addr)
        for addr in bond['address']:
            b.add_addr(addr)

        # remove no longer required service VLAN interfaces (vif-s)
        for vif_s in bond['vif_s_remove']:
            b.del_vlan(vif_s)

        # create service VLAN interfaces (vif-s)
        for vif_s in bond['vif_s']:
            s_vlan = b.add_vlan(vif_s['id'], ethertype=vif_s['ethertype'])
            apply_vlan_config(s_vlan, vif_s)

            # remove no longer required client VLAN interfaces (vif-c)
            # on lower service VLAN interface
            for vif_c in vif_s['vif_c_remove']:
                s_vlan.del_vlan(vif_c)

            # create client VLAN interfaces (vif-c)
            # on lower service VLAN interface
            for vif_c in vif_s['vif_c']:
                c_vlan = s_vlan.add_vlan(vif_c['id'])
                apply_vlan_config(c_vlan, vif_c)

        # remove no longer required VLAN interfaces (vif)
        for vif in bond['vif_remove']:
            b.del_vlan(vif)

        # create VLAN interfaces (vif)
        for vif in bond['vif']:
            vlan = b.add_vlan(vif['id'])
            apply_vlan_config(vlan, vif)

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
