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

    # get DHCP config dictionary and update values
    opt = vlan.get_dhcp_options()

    if config['dhcp_client_id']:
        opt['client_id'] = config['dhcp_client_id']

    if config['dhcp_hostname']:
        opt['hostname'] = config['dhcp_hostname']

    if config['dhcp_vendor_class_id']:
        opt['vendor_class_id'] = config['dhcp_vendor_class_id']

    # store DHCP config dictionary - used later on when addresses are aquired
    vlan.set_dhcp_options(opt)

    # get DHCPv6 config dictionary and update values
    opt = vlan.get_dhcpv6_options()

    if config['dhcpv6_prm_only']:
        opt['dhcpv6_prm_only'] = True

    if config['dhcpv6_temporary']:
        opt['dhcpv6_temporary'] = True

    # store DHCPv6 config dictionary - used later on when addresses are aquired
    vlan.set_dhcpv6_options(opt)

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
    # Maximum Transmission Unit (MTU)
    vlan.set_mtu(config['mtu'])

    # assign/remove VRF
    vlan.set_vrf(config['vrf'])

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

def verify_vlan_config(config):
    """
    Generic function to verify VLAN config consistency. Instead of re-
    implementing this function in multiple places use single source \o/
    """

    for vif in config['vif']:
        # DHCPv6 parameters-only and temporary address are mutually exclusive
        if vif['dhcpv6_prm_only'] and vif['dhcpv6_temporary']:
            raise ConfigError('DHCPv6 temporary and parameters-only options are mutually exclusive!')

        vrf_name = vif['vrf']
        if vrf_name and vrf_name not in interfaces():
            raise ConfigError(f'VRF "{vrf_name}" does not exist')

    # e.g. wireless interface has no vif_s support
    # thus we bail out eraly.
    if 'vif_s' not in config.keys():
        return

    for vif_s in config['vif_s']:
        for vif in config['vif']:
            if vif['id'] == vif_s['id']:
                raise ConfigError('Can not use identical ID on vif and vif-s interface')

        # DHCPv6 parameters-only and temporary address are mutually exclusive
        if vif_s['dhcpv6_prm_only'] and vif_s['dhcpv6_temporary']:
            raise ConfigError('DHCPv6 temporary and parameters-only options are mutually exclusive!')

            vrf_name = vif_s['vrf']
            if vrf_name and vrf_name not in interfaces():
                raise ConfigError(f'VRF "{vrf_name}" does not exist')

        for vif_c in vif_s['vif_c']:
            # DHCPv6 parameters-only and temporary address are mutually exclusive
            if vif_c['dhcpv6_prm_only'] and vif_c['dhcpv6_temporary']:
                raise ConfigError('DHCPv6 temporary and parameters-only options are mutually exclusive!')

            vrf_name = vif_c['vrf']
            if vrf_name and vrf_name not in interfaces():
                raise ConfigError(f'VRF "{vrf_name}" does not exist')


