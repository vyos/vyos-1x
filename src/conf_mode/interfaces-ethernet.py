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

from sys import exit
from copy import deepcopy
from netifaces import interfaces

from vyos.ifconfig import EthernetIf, Section
from vyos.ifconfig_vlan import apply_vlan_config, verify_vlan_config
from vyos.configdict import list_diff, intf_to_dict, add_to_dict
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
    'duplex': 'auto',
    'flow_control': 'on',
    'hw_id': '',
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
    'intf': '',
    'mac': '',
    'mtu': 1500,
    'offload_gro': 'off',
    'offload_gso': 'off',
    'offload_sg': 'off',
    'offload_tso': 'off',
    'offload_ufo': 'off',
    'speed': 'auto',
    'vif_s': [],
    'vif_s_remove': [],
    'vif': [],
    'vif_remove': [],
    'vrf': ''
}

def get_config():
    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    ifname = os.environ['VYOS_TAGNODE_VALUE']
    conf = Config()

    # check if ethernet interface has been removed
    cfg_base = ['interfaces', 'ethernet', ifname]
    if not conf.exists(cfg_base):
        eth = deepcopy(default_config_data)
        eth['intf'] = ifname
        eth['deleted'] = True
        # we can not bail out early as ethernet interface can not be removed
        # Kernel will complain with: RTNETLINK answers: Operation not supported.
        # Thus we need to remove individual settings
        return eth

    # set new configuration level
    conf.set_level(cfg_base)

    eth, disabled = intf_to_dict(conf, default_config_data)

    # disable ethernet flow control (pause frames)
    if conf.exists('disable-flow-control'):
        eth['flow_control'] = 'off'

    # retrieve real hardware address
    if conf.exists('hw-id'):
        eth['hw_id'] = conf.return_value('hw-id')

    # interface duplex
    if conf.exists('duplex'):
        eth['duplex'] = conf.return_value('duplex')

    # ARP cache entry timeout in seconds
    if conf.exists('ip arp-cache-timeout'):
        eth['ip_arp_cache_tmo'] = int(conf.return_value('ip arp-cache-timeout'))

    # Enable private VLAN proxy ARP on this interface
    if conf.exists('ip proxy-arp-pvlan'):
        eth['ip_proxy_arp_pvlan'] = 1

    # GRO (generic receive offload)
    if conf.exists('offload-options generic-receive'):
        eth['offload_gro'] = conf.return_value('offload-options generic-receive')

    # GSO (generic segmentation offload)
    if conf.exists('offload-options generic-segmentation'):
        eth['offload_gso'] = conf.return_value('offload-options generic-segmentation')

    # scatter-gather option
    if conf.exists('offload-options scatter-gather'):
        eth['offload_sg'] = conf.return_value('offload-options scatter-gather')

    # TSO (TCP segmentation offloading)
    if conf.exists('offload-options tcp-segmentation'):
        eth['offload_tso'] = conf.return_value('offload-options tcp-segmentation')

    # UDP fragmentation offloading
    if conf.exists('offload-options udp-fragmentation'):
        eth['offload_ufo'] = conf.return_value('offload-options udp-fragmentation')

    # interface speed
    if conf.exists('speed'):
        eth['speed'] = conf.return_value('speed')

    add_to_dict(conf, disabled, eth, 'vif', 'vif')
    add_to_dict(conf, disabled, eth, 'vif-s', 'vif_s')

    return eth


def verify(eth):
    if eth['deleted']:
        return None

    if eth['intf'] not in interfaces():
        raise ConfigError(f"Interface ethernet {eth['intf']} does not exist")

    if eth['speed'] == 'auto':
        if eth['duplex'] != 'auto':
            raise ConfigError('If speed is hardcoded, duplex must be hardcoded, too')

    if eth['duplex'] == 'auto':
        if eth['speed'] != 'auto':
            raise ConfigError('If duplex is hardcoded, speed must be hardcoded, too')

    if eth['dhcpv6_prm_only'] and eth['dhcpv6_temporary']:
        raise ConfigError('DHCPv6 temporary and parameters-only options are mutually exclusive!')

    vrf_name = eth['vrf']
    if vrf_name and vrf_name not in interfaces():
        raise ConfigError(f'VRF "{vrf_name}" does not exist')

    conf = Config()
    # some options can not be changed when interface is enslaved to a bond
    for bond in conf.list_nodes('interfaces bonding'):
        if conf.exists('interfaces bonding ' + bond + ' member interface'):
            bond_member = conf.return_values('interfaces bonding ' + bond + ' member interface')
            if eth['intf'] in bond_member:
                if eth['address']:
                    raise ConfigError(f"Can not assign address to interface {eth['intf']} which is a member of {bond}")

    # use common function to verify VLAN configuration
    verify_vlan_config(eth)
    return None

def generate(eth):
    return None

def apply(eth):
    e = EthernetIf(eth['intf'])
    if eth['deleted']:
        # delete interface
        e.remove()
    else:
        # update interface description used e.g. within SNMP
        e.set_alias(eth['description'])

        if eth['dhcp_client_id']:
            e.dhcp.v4.options['client_id'] = eth['dhcp_client_id']

        if eth['dhcp_hostname']:
            e.dhcp.v4.options['hostname'] = eth['dhcp_hostname']

        if eth['dhcp_vendor_class_id']:
            e.dhcp.v4.options['vendor_class_id'] = eth['dhcp_vendor_class_id']

        if eth['dhcpv6_prm_only']:
            e.dhcp.v6.options['dhcpv6_prm_only'] = True

        if eth['dhcpv6_temporary']:
            e.dhcp.v6.options['dhcpv6_temporary'] = True

        # ignore link state changes
        e.set_link_detect(eth['disable_link_detect'])
        # disable ethernet flow control (pause frames)
        e.set_flow_control(eth['flow_control'])
        # configure ARP cache timeout in milliseconds
        e.set_arp_cache_tmo(eth['ip_arp_cache_tmo'])
        # configure ARP filter configuration
        e.set_arp_filter(eth['ip_disable_arp_filter'])
        # configure ARP accept
        e.set_arp_accept(eth['ip_enable_arp_accept'])
        # configure ARP announce
        e.set_arp_announce(eth['ip_enable_arp_announce'])
        # configure ARP ignore
        e.set_arp_ignore(eth['ip_enable_arp_ignore'])
        # Enable proxy-arp on this interface
        e.set_proxy_arp(eth['ip_proxy_arp'])
        # Enable private VLAN proxy ARP on this interface
        e.set_proxy_arp_pvlan(eth['ip_proxy_arp_pvlan'])
        # IPv6 address autoconfiguration
        e.set_ipv6_autoconf(eth['ipv6_autoconf'])
        # IPv6 forwarding
        e.set_ipv6_forwarding(eth['ipv6_forwarding'])
        # IPv6 Duplicate Address Detection (DAD) tries
        e.set_ipv6_dad_messages(eth['ipv6_dup_addr_detect'])

        # Delete old IPv6 EUI64 addresses before changing MAC
        for addr in eth['ipv6_eui64_prefix_remove']:
            e.del_ipv6_eui64_address(addr)

        # Change interface MAC address - re-set to real hardware address (hw-id)
        # if custom mac is removed
        if eth['mac']:
            e.set_mac(eth['mac'])
        elif eth['hw_id']:
            e.set_mac(eth['hw_id'])

        # Add IPv6 EUI-based addresses
        for addr in eth['ipv6_eui64_prefix']:
            e.add_ipv6_eui64_address(addr)

        # Maximum Transmission Unit (MTU)
        e.set_mtu(eth['mtu'])

        # GRO (generic receive offload)
        e.set_gro(eth['offload_gro'])

        # GSO (generic segmentation offload)
        e.set_gso(eth['offload_gso'])

        # scatter-gather option
        e.set_sg(eth['offload_sg'])

        # TSO (TCP segmentation offloading)
        e.set_tso(eth['offload_tso'])

        # UDP fragmentation offloading
        e.set_ufo(eth['offload_ufo'])

        # Set physical interface speed and duplex
        e.set_speed_duplex(eth['speed'], eth['duplex'])

        # Enable/Disable interface
        if eth['disable']:
            e.set_admin_state('down')
        else:
            e.set_admin_state('up')

        # Configure interface address(es)
        # - not longer required addresses get removed first
        # - newly addresses will be added second
        for addr in eth['address_remove']:
            e.del_addr(addr)
        for addr in eth['address']:
            e.add_addr(addr)

        # assign/remove VRF
        e.set_vrf(eth['vrf'])

        # remove no longer required service VLAN interfaces (vif-s)
        for vif_s in eth['vif_s_remove']:
            e.del_vlan(vif_s)

        # create service VLAN interfaces (vif-s)
        for vif_s in eth['vif_s']:
            s_vlan = e.add_vlan(vif_s['id'], ethertype=vif_s['ethertype'])
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
        for vif in eth['vif_remove']:
            e.del_vlan(vif)

        # create VLAN interfaces (vif)
        for vif in eth['vif']:
            # QoS priority mapping can only be set during interface creation
            # so we delete the interface first if required.
            if vif['egress_qos_changed'] or vif['ingress_qos_changed']:
                try:
                    # on system bootup the above condition is true but the interface
                    # does not exists, which throws an exception, but that's legal
                    e.del_vlan(vif['id'])
                except:
                    pass

            vlan = e.add_vlan(vif['id'], ingress_qos=vif['ingress_qos'], egress_qos=vif['egress_qos'])
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
