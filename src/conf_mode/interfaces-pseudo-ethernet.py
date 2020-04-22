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
from vyos.configdict import list_diff, vlan_to_dict
from vyos.ifconfig import MACVLANIf
from vyos.ifconfig_vlan import apply_vlan_config, verify_vlan_config
from vyos.validate import is_bridge_member
from vyos import ConfigError

default_config_data = {
    'address': [],
    'address_remove': [],
    'description': '',
    'deleted': False,
    'dhcp_client_id': '',
    'dhcp_hostname': '',
    'dhcp_vendor_class_id': '',
    'dhcpv6_prm_only': False,
    'dhcpv6_temporary': False,
    'disable': False,
    'disable_link_detect': 1,
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
    'source_interface': '',
    'source_interface_changed': False,
    'mac': '',
    'mode': 'private',
    'vif_s': [],
    'vif_s_remove': [],
    'vif': [],
    'vif_remove': [],
    'vrf': ''
}

def get_config():
    peth = deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    peth['intf'] = os.environ['VYOS_TAGNODE_VALUE']
    cfg_base = ['interfaces', 'pseudo-ethernet', peth['intf']]

    # Check if interface has been removed
    if not conf.exists(cfg_base):
        peth['deleted'] = True
        # check if interface is member if a bridge
        peth['is_bridge_member'] = is_bridge_member(conf, peth['intf'])
        return peth

    # set new configuration level
    conf.set_level(cfg_base)

    # retrieve configured interface addresses
    if conf.exists(['address']):
        peth['address'] = conf.return_values(['address'])

    # get interface addresses (currently effective) - to determine which
    # address is no longer valid and needs to be removed
    eff_addr = conf.return_effective_values(['address'])
    peth['address_remove'] = list_diff(eff_addr, peth['address'])

    # retrieve interface description
    if conf.exists(['description']):
        peth['description'] = conf.return_value(['description'])

    # get DHCP client identifier
    if conf.exists(['dhcp-options', 'client-id']):
        peth['dhcp_client_id'] = conf.return_value(['dhcp-options', 'client-id'])

    # DHCP client host name (overrides the system host name)
    if conf.exists(['dhcp-options', 'host-name']):
        peth['dhcp_hostname'] = conf.return_value(['dhcp-options', 'host-name'])

    # DHCP client vendor identifier
    if conf.exists(['dhcp-options', 'vendor-class-id']):
        peth['dhcp_vendor_class_id'] = conf.return_value(['dhcp-options', 'vendor-class-id'])

    # DHCPv6 only acquire config parameters, no address
    if conf.exists(['dhcpv6-options parameters-only']):
        peth['dhcpv6_prm_only'] = True

    # DHCPv6 temporary IPv6 address
    if conf.exists(['dhcpv6-options temporary']):
        peth['dhcpv6_temporary'] = True

    # disable interface
    if conf.exists(['disable']):
        peth['disable'] = True

    # ignore link state changes
    if conf.exists(['disable-link-detect']):
        peth['disable_link_detect'] = 2

    # ARP cache entry timeout in seconds
    if conf.exists(['ip', 'arp-cache-timeout']):
        peth['ip_arp_cache_tmo'] = int(conf.return_value(['ip', 'arp-cache-timeout']))

    # ARP filter configuration
    if conf.exists(['ip', 'disable-arp-filter']):
        peth['ip_disable_arp_filter'] = 0

    # ARP enable accept
    if conf.exists(['ip', 'enable-arp-accept']):
        peth['ip_enable_arp_accept'] = 1

    # ARP enable announce
    if conf.exists(['ip', 'enable-arp-announce']):
        peth['ip_enable_arp_announce'] = 1

    # ARP enable ignore
    if conf.exists(['ip', 'enable-arp-ignore']):
        peth['ip_enable_arp_ignore'] = 1

    # Enable proxy-arp on this interface
    if conf.exists(['ip', 'enable-proxy-arp']):
        peth['ip_proxy_arp'] = 1

    # Enable private VLAN proxy ARP on this interface
    if conf.exists(['ip', 'proxy-arp-pvlan']):
        peth['ip_proxy_arp_pvlan'] = 1

    # Enable acquisition of IPv6 address using stateless autoconfig (SLAAC)
    if conf.exists('ipv6 address autoconf'):
        peth['ipv6_autoconf'] = 1

    # Get prefix for IPv6 addressing based on MAC address (EUI-64)
    if conf.exists('ipv6 address eui64'):
        peth['ipv6_eui64_prefix'].append(conf.return_value('ipv6 address eui64'))

    # Determine currently effective EUI64 address - to determine which
    # address is no longer valid and needs to be removed
    eff_addr = conf.return_effective_value('ipv6 address eui64')
    if eff_addr and eff_addr not in peth['ipv6_eui64_prefix']:
        peth['ipv6_eui64_prefix_remove'].append(eff_addr)

    # add the link-local by default to make IPv6 work
    peth['ipv6_eui64_prefix'].append('fe80::/64')

    # Disable IPv6 forwarding on this interface
    if conf.exists('ipv6 disable-forwarding'):
        peth['ipv6_forwarding'] = 0

    # IPv6 Duplicate Address Detection (DAD) tries
    if conf.exists('ipv6 dup-addr-detect-transmits'):
        peth['ipv6_dup_addr_detect'] = int(conf.return_value('ipv6 dup-addr-detect-transmits'))

    # Physical interface
    if conf.exists(['source-interface']):
        peth['source_interface'] = conf.return_value(['source-interface'])
        tmp = conf.return_effective_value(['source-interface'])
        if tmp != peth['source_interface']:
            peth['source_interface_changed'] = True

    # Media Access Control (MAC) address
    if conf.exists(['mac']):
        peth['mac'] = conf.return_value(['mac'])

    # MACvlan mode
    if conf.exists(['mode']):
        peth['mode'] = conf.return_value(['mode'])

    # retrieve VRF instance
    if conf.exists('vrf'):
        peth['vrf'] = conf.return_value('vrf')

    # re-set configuration level to parse new nodes
    conf.set_level(cfg_base)
    # get vif-s interfaces (currently effective) - to determine which vif-s
    # interface is no longer present and needs to be removed
    eff_intf = conf.list_effective_nodes('vif-s')
    act_intf = conf.list_nodes('vif-s')
    peth['vif_s_remove'] = list_diff(eff_intf, act_intf)

    if conf.exists('vif-s'):
        for vif_s in conf.list_nodes('vif-s'):
            # set config level to vif-s interface
            conf.set_level(cfg_base + ['vif-s', vif_s])
            peth['vif_s'].append(vlan_to_dict(conf))

    # re-set configuration level to parse new nodes
    conf.set_level(cfg_base)
    # Determine vif interfaces (currently effective) - to determine which
    # vif interface is no longer present and needs to be removed
    eff_intf = conf.list_effective_nodes('vif')
    act_intf = conf.list_nodes('vif')
    peth['vif_remove'] = list_diff(eff_intf, act_intf)

    if conf.exists('vif'):
        for vif in conf.list_nodes('vif'):
            # set config level to vif interface
            conf.set_level(cfg_base + ['vif', vif])
            peth['vif'].append(vlan_to_dict(conf))


    return peth

def verify(peth):
    if peth['deleted']:
        if peth['is_bridge_member']:
            interface = peth['intf']
            bridge = peth['is_bridge_member']
            raise ConfigError(f'Interface "{interface}" can not be deleted as it belongs to bridge "{bridge}"!')

        return None

    if not peth['source_interface']:
        raise ConfigError('Link device must be set for virtual ethernet {}'.format(peth['intf']))

    if not peth['source_interface'] in interfaces():
        raise ConfigError('Pseudo-ethernet source interface does not exist')

    vrf_name = peth['vrf']
    if vrf_name and vrf_name not in interfaces():
        raise ConfigError(f'VRF "{vrf_name}" does not exist')

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
    # IPv6 address autoconfiguration
    p.set_ipv6_autoconf(peth['ipv6_autoconf'])
    # IPv6 forwarding
    p.set_ipv6_forwarding(peth['ipv6_forwarding'])
    # IPv6 Duplicate Address Detection (DAD) tries
    p.set_ipv6_dad_messages(peth['ipv6_dup_addr_detect'])

    # assign/remove VRF
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

    # remove no longer required service VLAN interfaces (vif-s)
    for vif_s in peth['vif_s_remove']:
        p.del_vlan(vif_s)

    # create service VLAN interfaces (vif-s)
    for vif_s in peth['vif_s']:
        s_vlan = p.add_vlan(vif_s['id'], ethertype=vif_s['ethertype'])
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
    for vif in peth['vif_remove']:
        p.del_vlan(vif)

    # create VLAN interfaces (vif)
    for vif in peth['vif']:
        vlan = p.add_vlan(vif['id'])
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
