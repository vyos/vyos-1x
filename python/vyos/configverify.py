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
from vyos.util import dict_search

def verify_mtu(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation if the specified MTU can be used by the underlaying
    hardware.
    """
    from vyos.ifconfig import Interface
    if 'mtu' in config:
        mtu = int(config['mtu'])

        tmp = Interface(config['ifname'])
        min_mtu = tmp.get_min_mtu()
        max_mtu = tmp.get_max_mtu()

        if mtu < min_mtu:
            raise ConfigError(f'Interface MTU too low, ' \
                              f'minimum supported MTU is {min_mtu}!')
        if mtu > max_mtu:
            raise ConfigError(f'Interface MTU too high, ' \
                              f'maximum supported MTU is {max_mtu}!')

def verify_mtu_ipv6(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation if the specified MTU can be used when IPv6 is
    configured on the interface. IPv6 requires a 1280 bytes MTU.
    """
    from vyos.validate import is_ipv6
    if 'mtu' in config:
        # IPv6 minimum required link mtu
        min_mtu = 1280
        if int(config['mtu']) < min_mtu:
            interface = config['ifname']
            error_msg = f'IPv6 address will be configured on interface "{interface}" ' \
                        f'thus the minimum MTU requirement is {min_mtu}!'

            if not dict_search('ipv6.address.no_default_link_local', config):
                raise ConfigError('link-local ' + error_msg)

            for address in (dict_search('address', config) or []):
                if address in ['dhcpv6'] or is_ipv6(address):
                    raise ConfigError(error_msg)

            if dict_search('ipv6.address.autoconf', config):
                raise ConfigError(error_msg)

            if dict_search('ipv6.address.eui64', config):
                raise ConfigError(error_msg)


def verify_vrf(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation of VRF configuration.
    """
    from netifaces import interfaces
    if 'vrf' in config:
        if config['vrf'] not in interfaces():
            raise ConfigError('VRF "{vrf}" does not exist'.format(**config))

        if 'is_bridge_member' in config:
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
    if 'is_bridge_member' in config:
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
        raise ConfigError('Specified source-interface {source_interface} does '
                          'not exist'.format(**config))

    if 'source_interface_is_bridge_member' in config:
        raise ConfigError('Invalid source-interface {source_interface}. Interface '
                          'is already a member of bridge '
                          '{source_interface_is_bridge_member}'.format(**config))

    if 'source_interface_is_bond_member' in config:
        raise ConfigError('Invalid source-interface {source_interface}. Interface '
                          'is already a member of bond '
                          '{source_interface_is_bond_member}'.format(**config))

def verify_dhcpv6(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation of DHCPv6 options which are mutually exclusive.
    """
    if 'dhcpv6_options' in config:
        from vyos.util import dict_search

        if {'parameters_only', 'temporary'} <= set(config['dhcpv6_options']):
            raise ConfigError('DHCPv6 temporary and parameters-only options '
                              'are mutually exclusive!')

        # It is not allowed to have duplicate SLA-IDs as those identify an
        # assigned IPv6 subnet from a delegated prefix
        for pd in dict_search('dhcpv6_options.pd', config):
            sla_ids = []

            if not dict_search(f'dhcpv6_options.pd.{pd}.interface', config):
                raise ConfigError('DHCPv6-PD requires an interface where to assign '
                                  'the delegated prefix!')

            for interface in dict_search(f'dhcpv6_options.pd.{pd}.interface', config):
                sla_id = dict_search(
                    f'dhcpv6_options.pd.{pd}.interface.{interface}.sla_id', config)
                sla_ids.append(sla_id)

            # Check for duplicates
            duplicates = [x for n, x in enumerate(sla_ids) if x in sla_ids[:n]]
            if duplicates:
                raise ConfigError('Site-Level Aggregation Identifier (SLA-ID) '
                                  'must be unique per prefix-delegation!')

def verify_vlan_config(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation of interface VLANs
    """
    # 802.1q VLANs
    for vlan in config.get('vif', {}):
        vlan = config['vif'][vlan]
        verify_dhcpv6(vlan)
        verify_address(vlan)
        verify_vrf(vlan)

    # 802.1ad (Q-in-Q) VLANs
    for vlan in config.get('vif_s', {}):
        vlan = config['vif_s'][vlan]
        verify_dhcpv6(vlan)
        verify_address(vlan)
        verify_vrf(vlan)

        for vlan in config.get('vif_s', {}).get('vif_c', {}):
            vlan = config['vif_c'][vlan]
            verify_dhcpv6(vlan)
            verify_address(vlan)
            verify_vrf(vlan)

def verify_accel_ppp_base_service(config):
    """
    Common helper function which must be used by all Accel-PPP services based
    on get_config_dict()
    """
    # vertify auth settings
    if dict_search('authentication.mode', config) == 'local':
        if not dict_search('authentication.local_users', config):
            raise ConfigError('PPPoE local auth mode requires local users to be configured!')

        for user in dict_search('authentication.local_users.username', config):
            user_config = config['authentication']['local_users']['username'][user]

            if 'password' not in user_config:
                raise ConfigError(f'Password required for local user "{user}"')

            if 'rate_limit' in user_config:
                # if up/download is set, check that both have a value
                if not {'upload', 'download'} <= set(user_config['rate_limit']):
                    raise ConfigError(f'User "{user}" has rate-limit configured for only one ' \
                                      'direction but both upload and download must be given!')

    elif dict_search('authentication.mode', config) == 'radius':
        if not dict_search('authentication.radius.server', config):
            raise ConfigError('RADIUS authentication requires at least one server')

        for server in dict_search('authentication.radius.server', config):
            radius_config = config['authentication']['radius']['server'][server]
            if 'key' not in radius_config:
                raise ConfigError(f'Missing RADIUS secret key for server "{server}"')

    if 'gateway_address' not in config:
        raise ConfigError('PPPoE server requires gateway-address to be configured!')

    if 'name_server_ipv4' in config:
        if len(config['name_server_ipv4']) > 2:
            raise ConfigError('Not more then two IPv4 DNS name-servers ' \
                              'can be configured')

    if 'name_server_ipv6' in config:
        if len(config['name_server_ipv6']) > 3:
            raise ConfigError('Not more then three IPv6 DNS name-servers ' \
                              'can be configured')

    if 'client_ipv6_pool' in config:
        ipv6_pool = config['client_ipv6_pool']
        if 'delegate' in ipv6_pool:
            if 'prefix' not in ipv6_pool:
                raise ConfigError('IPv6 "delegate" also requires "prefix" to be defined!')

            for delegate in ipv6_pool['delegate']:
                if 'delegation_prefix' not in ipv6_pool['delegate'][delegate]:
                    raise ConfigError('delegation-prefix length required!')

