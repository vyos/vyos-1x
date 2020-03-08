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

from vyos.ifconfig import MACVLANIf
from vyos.ifconfig_vlan import apply_vlan_config, verify_vlan_config
from vyos.configdict import list_diff
from vyos.config import Config
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
    'ip_arp_cache_tmo': 30,
    'ip_disable_arp_filter': 1,
    'ip_enable_arp_accept': 0,
    'ip_enable_arp_announce': 0,
    'ip_enable_arp_ignore': 0,
    'ip_proxy_arp': 0,
    'ip_proxy_arp_pvlan': 0,
    'intf': '',
    'link': '',
    'link_changed': False,
    'mac': '',
    'mode': 'private',
    'vif_s': [],
    'vif_s_remove': [],
    'vif': [],
    'vif_remove': []
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

    # Lower link device
    if conf.exists(['link']):
        peth['link'] = conf.return_value(['link'])
        tmp = conf.return_effective_value(['link'])
        if tmp != peth['link']:
            peth['link_changed'] = True

    # Media Access Control (MAC) address
    if conf.exists(['mac']):
        peth['mac'] = conf.return_value(['mac'])

    # MACvlan mode
    if conf.exists(['mode']):
        peth['mode'] = conf.return_value(['mode'])

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
        return None

    if not peth['link']:
        raise ConfigError('Link device must be set for virtual ethernet {}'.format(peth['intf']))

    if not peth['link'] in interfaces():
        raise ConfigError('Pseudo-ethernet source interface does not exist')

    # use common function to verify VLAN configuration
    verify_vlan_config(peth)

    return None

def generate(peth):
    return None

def apply(peth):

    p = ''
    if peth['deleted']:
        # delete interface
        p = MACVLANIf(peth['intf'])
        p.remove()
        return None

    elif peth['link_changed']:
        # Check if MACVLAN interface already exists. Parameters like the
        # underlaying link device can not be changed  on the fly and the
        # interface needs to be recreated from the bottom.
        #
        # link_changed also means - the interface was not present in the
        # beginning and is newly created
        if peth['intf'] in interfaces():
            p = MACVLANIf(peth['intf'])
            p.remove()

        # MACVLAN interface needs to be created on-block instead of passing a ton
        # of arguments, I just use a dict that is managed by vyos.ifconfig
        conf = deepcopy(MACVLANIf.get_config())

        # Assign MACVLAN instance configuration parameters to config dict
        conf['link'] = peth['link']
        conf['mode'] = peth['mode']

        # It is safe to "re-create" the interface always, there is a sanity check
        # that the interface will only be create if its non existent
        p = MACVLANIf(peth['intf'], **conf)
    else:
        p = MACVLANIf(peth['intf'])

    # update interface description used e.g. within SNMP
    p.set_alias(peth['description'])

    # get DHCP config dictionary and update values
    opt = p.get_dhcp_options()

    if peth['dhcp_client_id']:
        opt['client_id'] = peth['dhcp_client_id']

    if peth['dhcp_hostname']:
        opt['hostname'] = peth['dhcp_hostname']

    if peth['dhcp_vendor_class_id']:
        opt['vendor_class_id'] = peth['dhcp_vendor_class_id']

    # store DHCP config dictionary - used later on when addresses are aquired
    p.set_dhcp_options(opt)

    # get DHCPv6 config dictionary and update values
    opt = p.get_dhcpv6_options()

    if peth['dhcpv6_prm_only']:
        opt['dhcpv6_prm_only'] = True

    if peth['dhcpv6_temporary']:
        opt['dhcpv6_temporary'] = True

    # store DHCPv6 config dictionary - used later on when addresses are aquired
    p.set_dhcpv6_options(opt)

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

    # Change interface MAC address
    if peth['mac']:
        p.set_mac(peth['mac'])

    # Change interface mode
    p.set_mode(peth['mode'])

    # Enable/Disable interface
    if peth['disable']:
        p.set_state('down')
    else:
        p.set_state('up')

    # Configure interface address(es)
    # - not longer required addresses get removed first
    # - newly addresses will be added second
    for addr in peth['address_remove']:
        p.del_addr(addr)
    for addr in peth['address']:
        p.add_addr(addr)

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
