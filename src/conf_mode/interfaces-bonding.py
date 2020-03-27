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

from vyos.ifconfig import BondIf
from vyos.ifconfig_vlan import apply_vlan_config, verify_vlan_config
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
    'ip_disable_arp_filter': 1,
    'ip_enable_arp_accept': 0,
    'ip_enable_arp_announce': 0,
    'ip_enable_arp_ignore': 0,
    'ip_proxy_arp': 0,
    'ip_proxy_arp_pvlan': 0,
    'ipv6_autoconf': 0,
    'ipv6_forwarding': 1,
    'ipv6_dup_addr_detect': 1,
    'intf': '',
    'mac': '',
    'mode': '802.3ad',
    'member': [],
    'shutdown_required': False,
    'mtu': 1500,
    'primary': '',
    'vif_s': [],
    'vif_s_remove': [],
    'vif': [],
    'vif_remove': [],
    'vrf': ''
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
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    bond['intf'] = os.environ['VYOS_TAGNODE_VALUE']

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
        bond['dhcpv6_prm_only'] = True

    # DHCPv6 temporary IPv6 address
    if conf.exists('dhcpv6-options temporary'):
        bond['dhcpv6_temporary'] = True

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

    # ARP filter configuration
    if conf.exists('ip disable-arp-filter'):
        bond['ip_disable_arp_filter'] = 0

    # ARP enable accept
    if conf.exists('ip enable-arp-accept'):
        bond['ip_enable_arp_accept'] = 1

    # ARP enable announce
    if conf.exists('ip enable-arp-announce'):
        bond['ip_enable_arp_announce'] = 1

    # ARP enable ignore
    if conf.exists('ip enable-arp-ignore'):
        bond['ip_enable_arp_ignore'] = 1

    # Enable proxy-arp on this interface
    if conf.exists('ip enable-proxy-arp'):
        bond['ip_proxy_arp'] = 1

    # Enable private VLAN proxy ARP on this interface
    if conf.exists('ip proxy-arp-pvlan'):
        bond['ip_proxy_arp_pvlan'] = 1

    # Enable acquisition of IPv6 address using stateless autoconfig (SLAAC)
    if conf.exists('ipv6 address autoconf'):
        bond['ipv6_autoconf'] = 1

    # Disable IPv6 forwarding on this interface
    if conf.exists('ipv6 disable-forwarding'):
        bond['ipv6_forwarding'] = 0

    # IPv6 Duplicate Address Detection (DAD) tries
    if conf.exists('ipv6 dup-addr-detect-transmits'):
        bond['ipv6_dup_addr_detect'] = int(conf.return_value('ipv6 dup-addr-detect-transmits'))

    # Media Access Control (MAC) address
    if conf.exists('mac'):
        bond['mac'] = conf.return_value('mac')

    # Bonding mode
    if conf.exists('mode'):
        act_mode = conf.return_value('mode')
        eff_mode = conf.return_effective_value('mode')
        if not (act_mode == eff_mode):
            bond['shutdown_required'] = True

        bond['mode'] = get_bond_mode(act_mode)

    # Maximum Transmission Unit (MTU)
    if conf.exists('mtu'):
        bond['mtu'] = int(conf.return_value('mtu'))

    # determine bond member interfaces (currently configured)
    if conf.exists('member interface'):
        bond['member'] = conf.return_values('member interface')

        # We can not call conf.return_effective_values() as it would not work
        # on reboots. Reboots/First boot will return that running config and
        # saved config is the same, thus on a reboot the bond members will
        # not be added all (https://phabricator.vyos.net/T2030)
        live_members = BondIf(bond['intf']).get_slaves()
        if not (bond['member'] == live_members):
            bond['shutdown_required'] = True

    # Primary device interface
    if conf.exists('primary'):
        bond['primary'] = conf.return_value('primary')

    # retrieve VRF instance
    if conf.exists('vrf'):
        bond['vrf'] = conf.return_value('vrf')

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

    vrf_name = bond['vrf']
    if vrf_name and vrf_name not in interfaces():
        raise ConfigError(f'VRF "{vrf_name}" does not exist')

    # use common function to verify VLAN configuration
    verify_vlan_config(bond)

    conf = Config()
    for intf in bond['member']:
        # check if member interface is "real"
        if intf not in interfaces():
            raise ConfigError('interface {} does not exist!'.format(intf))

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

        # store DHCP config dictionary - used later on when addresses are aquired
        b.set_dhcp_options(opt)

        # get DHCPv6 config dictionary and update values
        opt = b.get_dhcpv6_options()

        if bond['dhcpv6_prm_only']:
            opt['dhcpv6_prm_only'] = True

        if bond['dhcpv6_temporary']:
            opt['dhcpv6_temporary'] = True

        # store DHCPv6 config dictionary - used later on when addresses are required
        b.set_dhcpv6_options(opt)

        # ignore link state changes
        b.set_link_detect(bond['disable_link_detect'])
        # Bonding transmit hash policy
        b.set_hash_policy(bond['hash_policy'])
        # configure ARP cache timeout in milliseconds
        b.set_arp_cache_tmo(bond['ip_arp_cache_tmo'])
        # configure ARP filter configuration
        b.set_arp_filter(bond['ip_disable_arp_filter'])
        # configure ARP accept
        b.set_arp_accept(bond['ip_enable_arp_accept'])
        # configure ARP announce
        b.set_arp_announce(bond['ip_enable_arp_announce'])
        # configure ARP ignore
        b.set_arp_ignore(bond['ip_enable_arp_ignore'])
        # Enable proxy-arp on this interface
        b.set_proxy_arp(bond['ip_proxy_arp'])
        # Enable private VLAN proxy ARP on this interface
        b.set_proxy_arp_pvlan(bond['ip_proxy_arp_pvlan'])
        # IPv6 address autoconfiguration
        b.set_ipv6_autoconf(bond['ipv6_autoconf'])
        # IPv6 forwarding
        b.set_ipv6_forwarding(bond['ipv6_forwarding'])
        # IPv6 Duplicate Address Detection (DAD) tries
        b.set_ipv6_dad_messages(bond['ipv6_dup_addr_detect'])

        # Change interface MAC address
        if bond['mac']:
            b.set_mac(bond['mac'])

        # Maximum Transmission Unit (MTU)
        b.set_mtu(bond['mtu'])

        # Primary device interface
        if bond['primary']:
            b.set_primary(bond['primary'])

        # Some parameters can not be changed when the bond is up.
        if bond['shutdown_required']:
            # Disable bond prior changing of certain properties
            b.set_admin_state('down')

            # The bonding mode can not be changed when there are interfaces enslaved
            # to this bond, thus we will free all interfaces from the bond first!
            for intf in b.get_slaves():
                b.del_port(intf)

            # Bonding policy/mode
            b.set_mode(bond['mode'])

            # Add (enslave) interfaces to bond
            for intf in bond['member']:
                b.add_port(intf)

        # As the bond interface is always disabled first when changing
        # parameters we will only re-enable the interface if it is not
        # administratively disabled
        if not bond['disable']:
            b.set_admin_state('up')
        else:
            b.set_admin_state('down')

        # Configure interface address(es)
        # - not longer required addresses get removed first
        # - newly addresses will be added second
        for addr in bond['address_remove']:
            b.del_addr(addr)
        for addr in bond['address']:
            b.add_addr(addr)

        # assign/remove VRF
        b.set_vrf(bond['vrf'])

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
