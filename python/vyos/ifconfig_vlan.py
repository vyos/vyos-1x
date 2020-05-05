# Copyright 2019-2020 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

from netifaces import interfaces
from vyos import ConfigError

def apply_vlan_config(vlan, config):
    """
    Generic function to apply a VLAN configuration from a dictionary
    to a VLAN interface
    """

    if not vlan.definition['vlan']:
        raise TypeError()

    if config['dhcp_client_id']:
        vlan.dhcp.v4.options['client_id'] = config['dhcp_client_id']

    if config['dhcp_hostname']:
        vlan.dhcp.v4.options['hostname'] = config['dhcp_hostname']

    if config['dhcp_vendor_class_id']:
        vlan.dhcp.v4.options['vendor_class_id'] = config['dhcp_vendor_class_id']

    if config['dhcpv6_prm_only']:
        vlan.dhcp.v6.options['dhcpv6_prm_only'] = True

    if config['dhcpv6_temporary']:
        vlan.dhcp.v6.options['dhcpv6_temporary'] = True

    # update interface description used e.g. within SNMP
    vlan.set_alias(config['description'])
    # ignore link state changes
    vlan.set_link_detect(config['disable_link_detect'])
    # configure ARP filter configuration
    vlan.set_arp_filter(config['ip_disable_arp_filter'])
    # configure ARP accept
    vlan.set_arp_accept(config['ip_enable_arp_accept'])
    # configure ARP announce
    vlan.set_arp_announce(config['ip_enable_arp_announce'])
    # configure ARP ignore
    vlan.set_arp_ignore(config['ip_enable_arp_ignore'])
    # configure Proxy ARP
    vlan.set_proxy_arp(config['ip_proxy_arp'])
    # IPv6 address autoconfiguration
    vlan.set_ipv6_autoconf(config['ipv6_autoconf'])
    # IPv6 forwarding
    vlan.set_ipv6_forwarding(config['ipv6_forwarding'])
    # IPv6 Duplicate Address Detection (DAD) tries
    vlan.set_ipv6_dad_messages(config['ipv6_dup_addr_detect'])
    # Maximum Transmission Unit (MTU)
    vlan.set_mtu(config['mtu'])

    # assign/remove VRF (ONLY when not a member of a bridge,
    # otherwise 'nomaster' removes it from it)
    if not config['is_bridge_member']:
        vlan.set_vrf(config['vrf'])

    # Delete old IPv6 EUI64 addresses before changing MAC
    for addr in config['ipv6_eui64_prefix_remove']:
        vlan.del_ipv6_eui64_address(addr)

    # Change VLAN interface MAC address
    if config['mac']:
        vlan.set_mac(config['mac'])

    # Add IPv6 EUI-based addresses
    for addr in config['ipv6_eui64_prefix']:
        vlan.add_ipv6_eui64_address(addr)

    # enable/disable VLAN interface
    if config['disable']:
        vlan.set_admin_state('down')
    else:
        vlan.set_admin_state('up')

    # Configure interface address(es)
    # - not longer required addresses get removed first
    # - newly addresses will be added second
    for addr in config['address_remove']:
        vlan.del_addr(addr)
    for addr in config['address']:
        vlan.add_addr(addr)

    # re-add ourselves to any bridge we might have fallen out of
    if config['is_bridge_member']:
        vlan.add_to_bridge(config['is_bridge_member'])

def verify_vlan_config(config):
    """
    Generic function to verify VLAN config consistency. Instead of re-
    implementing this function in multiple places use single source \o/
    """

    # config['vif'] is a dict with ids as keys and config dicts as values
    for vif in config['vif'].values():
        # DHCPv6 parameters-only and temporary address are mutually exclusive
        if vif['dhcpv6_prm_only'] and vif['dhcpv6_temporary']:
            raise ConfigError('DHCPv6 temporary and parameters-only options are mutually exclusive!')

        if ( vif['is_bridge_member']
                and ( vif['address']
                    or vif['ipv6_eui64_prefix']
                    or vif['ipv6_autoconf'] ) ):
            raise ConfigError((
                    f'Cannot assign address to vif interface {vif["intf"]} '
                    f'which is a member of bridge {vif["is_bridge_member"]}'))

        if vif['vrf']:
            if vif['vrf'] not in interfaces():
                raise ConfigError(f'VRF "{vif["vrf"]}" does not exist')

            if vif['is_bridge_member']:
                raise ConfigError((
                    f'vif {vif["intf"]} cannot be member of VRF {vif["vrf"]} '
                    f'and bridge {vif["is_bridge_member"]} at the same time!'))

    # e.g. wireless interface has no vif_s support
    # thus we bail out eraly.
    if 'vif_s' not in config.keys():
        return

    # config['vif_s'] is a dict with ids as keys and config dicts as values
    for vif_s_id, vif_s in config['vif_s'].items():
        for vif_id, vif in config['vif'].items():
            if vif_id == vif_s_id:
                raise ConfigError((
                    f'Cannot use identical ID on vif "{vif["intf"]}" '
                    f'and vif-s "{vif_s}"'))

        # DHCPv6 parameters-only and temporary address are mutually exclusive
        if vif_s['dhcpv6_prm_only'] and vif_s['dhcpv6_temporary']:
            raise ConfigError((
                'DHCPv6 temporary and parameters-only options are mutually '
                'exclusive!'))

        if ( vif_s['is_bridge_member']
                and ( vif_s['address']
                    or vif_s['ipv6_eui64_prefix']
                    or vif_s['ipv6_autoconf'] ) ):
            raise ConfigError((
                    f'Cannot assign address to vif-s interface {vif_s["intf"]} '
                    f'which is a member of bridge {vif_s["is_bridge_member"]}'))

        if vif_s['vrf']:
            if vif_s['vrf'] not in interfaces():
                raise ConfigError(f'VRF "{vif_s["vrf"]}" does not exist')

            if vif_s['is_bridge_member']:
                raise ConfigError((
                    f'vif-s {vif_s["intf"]} cannot be member of VRF {vif_s["vrf"]} '
                    f'and bridge {vif_s["is_bridge_member"]} at the same time!'))

        # vif_c is a dict with ids as keys and config dicts as values
        for vif_c in vif_s['vif_c'].values():
            # DHCPv6 parameters-only and temporary address are mutually exclusive
            if vif_c['dhcpv6_prm_only'] and vif_c['dhcpv6_temporary']:
                raise ConfigError((
                    'DHCPv6 temporary and parameters-only options are '
                    'mutually exclusive!'))

            if ( vif_c['is_bridge_member']
                    and ( vif_c['address']
                        or vif_c['ipv6_eui64_prefix']
                        or vif_c['ipv6_autoconf'] ) ):
                raise ConfigError((
                    f'Cannot assign address to vif-c interface {vif_c["intf"]} '
                    f'which is a member of bridge {vif_c["is_bridge_member"]}'))

            if vif_c['vrf']:
                if vif_c['vrf'] not in interfaces():
                    raise ConfigError(f'VRF "{vif_c["vrf"]}" does not exist')

                if vif_c['is_bridge_member']:
                    raise ConfigError((
                    f'vif-c {vif_c["intf"]} cannot be member of VRF {vif_c["vrf"]} '
                    f'and bridge {vif_c["is_bridge_member"]} at the same time!'))

