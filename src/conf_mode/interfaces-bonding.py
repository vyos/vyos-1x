#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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

from vyos.ifconfig import BondIf, Section
from vyos.ifconfig_vlan import apply_vlan_config, verify_vlan_config
from vyos.configdict import list_diff, intf_to_dict, add_to_dict
from vyos.config import Config
from vyos.util import call, cmd
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
    'intf': '',
    'ip_arp_cache_tmo': 30,
    'ip_disable_arp_filter': 1,
    'ip_enable_arp_accept': 0,
    'ip_enable_arp_announce': 0,
    'ip_enable_arp_ignore': 0,
    'ip_proxy_arp': 0,
    'ip_proxy_arp_pvlan': 0,
    'ipv6_autoconf': 0,
    'ipv6_eui64_prefix': [],
    'ipv6_eui64_prefix_remove': [],
    'ipv6_forwarding': 1,
    'ipv6_dup_addr_detect': 1,
    'is_bridge_member': False,
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
    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    ifname = os.environ['VYOS_TAGNODE_VALUE']
    conf = Config()

    # initialize kernel module if not loaded
    if not os.path.isfile('/sys/class/net/bonding_masters'):
        import syslog
        syslog.syslog(syslog.LOG_NOTICE, "loading bonding kernel module")
        if call('modprobe bonding max_bonds=0 miimon=250') != 0:
            syslog.syslog(syslog.LOG_NOTICE, "failed loading bonding kernel module")
            raise ConfigError("failed loading bonding kernel module")

    # check if bond has been removed
    cfg_base = 'interfaces bonding ' + ifname
    if not conf.exists(cfg_base):
        bond = deepcopy(default_config_data)
        bond['intf'] = ifname
        bond['deleted'] = True
        return bond

    # set new configuration level
    conf.set_level(cfg_base)

    bond, disabled = intf_to_dict(conf, default_config_data)

    # ARP link monitoring frequency in milliseconds
    if conf.exists('arp-monitor interval'):
        bond['arp_mon_intvl'] = int(conf.return_value('arp-monitor interval'))

    # IP address to use for ARP monitoring
    if conf.exists('arp-monitor target'):
        bond['arp_mon_tgt'] = conf.return_values('arp-monitor target')

    # Bonding transmit hash policy
    if conf.exists('hash-policy'):
        bond['hash_policy'] = conf.return_value('hash-policy')

    # ARP cache entry timeout in seconds
    if conf.exists('ip arp-cache-timeout'):
        bond['ip_arp_cache_tmo'] = int(conf.return_value('ip arp-cache-timeout'))

    # Enable private VLAN proxy ARP on this interface
    if conf.exists('ip proxy-arp-pvlan'):
        bond['ip_proxy_arp_pvlan'] = 1

    # Bonding mode
    if conf.exists('mode'):
        act_mode = conf.return_value('mode')
        eff_mode = conf.return_effective_value('mode')
        if not (act_mode == eff_mode):
            bond['shutdown_required'] = True

        bond['mode'] = get_bond_mode(act_mode)

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

    add_to_dict(conf, disabled, bond, 'vif', 'vif')
    add_to_dict(conf, disabled, bond, 'vif-s', 'vif_s')

    return bond


def verify(bond):
    if bond['deleted']:
        if bond['is_bridge_member']:
            interface = bond['intf']
            bridge = bond['is_bridge_member']
            raise ConfigError(f'Interface "{interface}" can not be deleted as it belongs to bridge "{bridge}"!')
        return None

    if len (bond['arp_mon_tgt']) > 16:
        raise ConfigError('The maximum number of targets that can be specified is 16')

    if bond['primary']:
        if bond['mode'] not in ['active-backup', 'balance-tlb', 'balance-alb']:
            raise ConfigError('Mode dependency failed, primary not supported ' \
                              'in mode "{}"!'.format(bond['mode']))

    if bond['vrf']:
        if bond['vrf'] not in interfaces():
            raise ConfigError(f'VRF "{bond["vrf"]}" does not exist')

        if bond['is_bridge_member']:
            raise ConfigError((
                f'Interface "{bond["intf"]}" cannot be member of VRF '
                f'"{bond["vrf"]}" and bridge {bond["is_bridge_member"]} '
                f'at the same time!'))

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

        if bond['dhcp_client_id']:
            b.dhcp.v4.options['client_id'] = bond['dhcp_client_id']

        if bond['dhcp_hostname']:
            b.dhcp.v4.options['hostname'] = bond['dhcp_hostname']

        if bond['dhcp_vendor_class_id']:
            b.dhcp.v4.options['vendor_class_id'] = bond['dhcp_vendor_class_id']

        if bond['dhcpv6_prm_only']:
            b.dhcp.v6.options['dhcpv6_prm_only'] = True

        if bond['dhcpv6_temporary']:
            b.dhcp.v6.options['dhcpv6_temporary'] = True

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

        # Delete old IPv6 EUI64 addresses before changing MAC
        for addr in bond['ipv6_eui64_prefix_remove']:
            b.del_ipv6_eui64_address(addr)

        # Change interface MAC address
        if bond['mac']:
            b.set_mac(bond['mac'])

        # Add IPv6 EUI-based addresses
        for addr in bond['ipv6_eui64_prefix']:
            b.add_ipv6_eui64_address(addr)

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
                # flushes only children of Interfaces class (e.g. vlan are not)
                if intf in Section.interfaces():
                    klass = Section.klass(intf, vlan=False)
                    klass(intf, create=False).flush_addrs()
                # flushes also vlan interfaces
                call(f'ip addr flush dev "{intf}"')
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
