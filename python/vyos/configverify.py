# Copyright 2020 VyOS maintainers and contributors <maintainers@vyos.io>
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

# The sole purpose of this module is to hold common functions used in
# all kinds of implementations to verify the CLI configuration.
# It is started by migrating the interfaces to the new get_config_dict()
# approach which will lead to a lot of code that can be reused.

# NOTE: imports should be as local as possible to the function which
# makes use of it!

from vyos import ConfigError

def verify_vrf(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation of VRF configuration.
    """
    from netifaces import interfaces
    if 'vrf' in config.keys():
        if config['vrf'] not in interfaces():
            raise ConfigError('VRF "{vrf}" does not exist'.format(**config))

        if 'is_bridge_member' in config.keys():
            raise ConfigError(
                'Interface "{ifname}" cannot be both a member of VRF "{vrf}" '
                'and bridge "{is_bridge_member}"!'.format(**config))


def verify_address(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation of IP address assignment when interface is part
    of a bridge or bond.
    """
    if {'is_bridge_member', 'address'} <= set(config):
        raise ConfigError(
            'Cannot assign address to interface "{ifname}" as it is a '
            'member of bridge "{is_bridge_member}"!'.format(**config))


def verify_bridge_delete(config):
    """
    Common helper function used by interface implementations to
    perform recurring validation of IP address assignmenr
    when interface also is part of a bridge.
    """
    if 'is_bridge_member' in config.keys():
        raise ConfigError(
            'Interface "{ifname}" cannot be deleted as it is a '
            'member of bridge "{is_bridge_member}"!'.format(**config))

def verify_interface_exists(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation if an interface actually exists.
    """
    from netifaces import interfaces
    if not config['ifname'] in interfaces():
        raise ConfigError('Interface "{ifname}" does not exist!'
                          .format(**config))

def verify_source_interface(config):
    """
    Common helper function used by interface implementations to
    perform recurring validation of the existence of a source-interface
    required by e.g. peth/MACvlan, MACsec ...
    """
    from netifaces import interfaces
    if 'source_interface' not in config:
        raise ConfigError('Physical source-interface required for '
                          'interface "{ifname}"'.format(**config))
    if config['source_interface'] not in interfaces():
        raise ConfigError('Source interface {source_interface} does not '
                          'exist'.format(**config))

def verify_dhcpv6(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation of DHCPv6 options which are mutually exclusive.
    """
    if {'parameters_only', 'temporary'} <= set(config.get('dhcpv6_options', {})):
        raise ConfigError('DHCPv6 temporary and parameters-only options '
                          'are mutually exclusive!')

def verify_vlan_config(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation of interface VLANs
    """
    # 802.1q VLANs
    for vlan in config.get('vif', {}).keys():
        vlan = config['vif'][vlan]
        verify_dhcpv6(vlan)
        verify_address(vlan)
        verify_vrf(vlan)

    # 802.1ad (Q-in-Q) VLANs
    for vlan in config.get('vif_s', {}).keys():
        vlan = config['vif_s'][vlan]
        verify_dhcpv6(vlan)
        verify_address(vlan)
        verify_vrf(vlan)

        for vlan in config.get('vif_s', {}).get('vif_c', {}).keys():
            vlan = config['vif_c'][vlan]
            verify_dhcpv6(vlan)
            verify_address(vlan)
            verify_vrf(vlan)
