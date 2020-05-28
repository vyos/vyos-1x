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

from vyos.config import Config
from vyos.configdict import list_diff, intf_to_dict, add_to_dict, interface_default_data
from vyos.ifconfig import MACVLANIf, Section
from vyos.ifconfig_vlan import apply_all_vlans, verify_vlan_config
from vyos import ConfigError

default_config_data = {
    **interface_default_data,
    'deleted': False,
    'intf': '',
    'ip_arp_cache_tmo': 30,
    'ip_proxy_arp_pvlan': 0,
    'source_interface': '',
    'source_interface_changed': False,
    'mode': 'private',
    'vif_s': {},
    'vif_s_remove': [],
    'vif': {},
    'vif_remove': [],
    'vrf': ''
}

def get_config():
    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    ifname = os.environ['VYOS_TAGNODE_VALUE']
    conf = Config()

    # Check if interface has been removed
    cfg_base = ['interfaces', 'pseudo-ethernet', ifname]
    if not conf.exists(cfg_base):
        peth = deepcopy(default_config_data)
        peth['deleted'] = True
        return peth

    # set new configuration level
    conf.set_level(cfg_base)

    peth, disabled = intf_to_dict(conf, default_config_data)

    # ARP cache entry timeout in seconds
    if conf.exists(['ip', 'arp-cache-timeout']):
        peth['ip_arp_cache_tmo'] = int(conf.return_value(['ip', 'arp-cache-timeout']))

    # Enable private VLAN proxy ARP on this interface
    if conf.exists(['ip', 'proxy-arp-pvlan']):
        peth['ip_proxy_arp_pvlan'] = 1

    # Physical interface
    if conf.exists(['source-interface']):
        peth['source_interface'] = conf.return_value(['source-interface'])
        tmp = conf.return_effective_value(['source-interface'])
        if tmp != peth['source_interface']:
            peth['source_interface_changed'] = True

    # MACvlan mode
    if conf.exists(['mode']):
        peth['mode'] = conf.return_value(['mode'])

    add_to_dict(conf, disabled, peth, 'vif', 'vif')
    add_to_dict(conf, disabled, peth, 'vif-s', 'vif_s')

    return peth

def verify(peth):
    if peth['deleted']:
        if peth['is_bridge_member']:
            raise ConfigError((
                f'Cannot delete interface "{peth["intf"]}" as it is a '
                f'member of bridge "{peth["is_bridge_member"]}"!'))

        return None

    if not peth['source_interface']:
        raise ConfigError((
            f'Link device must be set for pseudo-ethernet "{peth["intf"]}"'))

    if not peth['source_interface'] in interfaces():
        raise ConfigError((
            f'Pseudo-ethernet "{peth["intf"]}" link device does not exist'))

    if ( peth['is_bridge_member']
            and ( peth['address']
                or peth['ipv6_eui64_prefix']
                or peth['ipv6_autoconf'] ) ):
        raise ConfigError((
            f'Cannot assign address to interface "{peth["intf"]}" '
            f'as it is a member of bridge "{peth["is_bridge_member"]}"!'))

    if peth['vrf']:
        if peth['vrf'] not in interfaces():
            raise ConfigError(f'VRF "{peth["vrf"]}" does not exist')

        if peth['is_bridge_member']:
            raise ConfigError((
                f'Interface "{peth["intf"]}" cannot be member of VRF '
                f'"{peth["vrf"]}" and bridge {peth["is_bridge_member"]} '
                f'at the same time!'))

    # use common function to verify VLAN configuration
    verify_vlan_config(peth)
    return None

def generate(peth):
    return None

def apply(peth):
    if peth['deleted']:
        # delete interface
        MACVLANIf(peth['intf']).remove()
        return None

    # Check if MACVLAN interface already exists. Parameters like the underlaying
    # source-interface device can not be changed on the fly and the interface
    # needs to be recreated from the bottom.
    if peth['intf'] in interfaces():
        if peth['source_interface_changed']:
            MACVLANIf(peth['intf']).remove()

    # MACVLAN interface needs to be created on-block instead of passing a ton
    # of arguments, I just use a dict that is managed by vyos.ifconfig
    conf = deepcopy(MACVLANIf.get_config())

    # Assign MACVLAN instance configuration parameters to config dict
    conf['source_interface'] = peth['source_interface']
    conf['mode'] = peth['mode']

    # It is safe to "re-create" the interface always, there is a sanity check
    # that the interface will only be create if its non existent
    p = MACVLANIf(peth['intf'], **conf)

    # update interface description used e.g. within SNMP
    p.set_alias(peth['description'])

    if peth['dhcp_client_id']:
        p.dhcp.v4.options['client_id'] = peth['dhcp_client_id']

    if peth['dhcp_hostname']:
        p.dhcp.v4.options['hostname'] = peth['dhcp_hostname']

    if peth['dhcp_vendor_class_id']:
        p.dhcp.v4.options['vendor_class_id'] = peth['dhcp_vendor_class_id']

    if peth['dhcpv6_prm_only']:
        p.dhcp.v6.options['dhcpv6_prm_only'] = True

    if peth['dhcpv6_temporary']:
        p.dhcp.v6.options['dhcpv6_temporary'] = True

    if peth['dhcpv6_pd_length']:
        p.dhcp.v6.options['dhcpv6_pd_length'] = peth['dhcpv6_pd_length']

    if peth['dhcpv6_pd_interfaces']:
        p.dhcp.v6.options['dhcpv6_pd_interfaces'] = peth['dhcpv6_pd_interfaces']

    # ignore link state changes
    p.set_link_detect(peth['disable_link_detect'])
    # configure ARP cache timeout in milliseconds
    p.set_arp_cache_tmo(peth['ip_arp_cache_tmo'])
    # configure ARP filter configuration
    p.set_arp_filter(peth['ip_disable_arp_filter'])
    # configure ARP accept
    p.set_arp_accept(peth['ip_enable_arp_accept'])
    # configure ARP announce
    p.set_arp_announce(peth['ip_enable_arp_announce'])
    # configure ARP ignore
    p.set_arp_ignore(peth['ip_enable_arp_ignore'])
    # Enable proxy-arp on this interface
    p.set_proxy_arp(peth['ip_proxy_arp'])
    # Enable private VLAN proxy ARP on this interface
    p.set_proxy_arp_pvlan(peth['ip_proxy_arp_pvlan'])
    # IPv6 accept RA
    p.set_ipv6_accept_ra(peth['ipv6_accept_ra'])
    # IPv6 address autoconfiguration
    p.set_ipv6_autoconf(peth['ipv6_autoconf'])
    # IPv6 forwarding
    p.set_ipv6_forwarding(peth['ipv6_forwarding'])
    # IPv6 Duplicate Address Detection (DAD) tries
    p.set_ipv6_dad_messages(peth['ipv6_dup_addr_detect'])

    # assign/remove VRF (ONLY when not a member of a bridge,
    # otherwise 'nomaster' removes it from it)
    if not peth['is_bridge_member']:
        p.set_vrf(peth['vrf'])

    # Delete old IPv6 EUI64 addresses before changing MAC
    for addr in peth['ipv6_eui64_prefix_remove']:
        p.del_ipv6_eui64_address(addr)

    # Change interface MAC address
    if peth['mac']:
        p.set_mac(peth['mac'])

    # Add IPv6 EUI-based addresses
    for addr in peth['ipv6_eui64_prefix']:
        p.add_ipv6_eui64_address(addr)

    # Change interface mode
    p.set_mode(peth['mode'])

    # Enable/Disable interface
    if peth['disable']:
        p.set_admin_state('down')
    else:
        p.set_admin_state('up')

    # Configure interface address(es)
    # - not longer required addresses get removed first
    # - newly addresses will be added second
    for addr in peth['address_remove']:
        p.del_addr(addr)
    for addr in peth['address']:
        p.add_addr(addr)

    # re-add ourselves to any bridge we might have fallen out of
    if peth['is_bridge_member']:
        p.add_to_bridge(peth['is_bridge_member'])

    # apply all vlans to interface
    apply_all_vlans(p, peth)

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
