# Copyright 2020-2022 VyOS maintainers and contributors <maintainers@vyos.io>
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

def verify_mtu_parent(config, parent):
    if 'mtu' not in config or 'mtu' not in parent:
        return

    mtu = int(config['mtu'])
    parent_mtu = int(parent['mtu'])
    if mtu > parent_mtu:
        raise ConfigError(f'Interface MTU ({mtu}) too high, ' \
                          f'parent interface MTU is {parent_mtu}!')

def verify_mtu_ipv6(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation if the specified MTU can be used when IPv6 is
    configured on the interface. IPv6 requires a 1280 bytes MTU.
    """
    from vyos.template import is_ipv6
    if 'mtu' in config:
        # IPv6 minimum required link mtu
        min_mtu = 1280
        if int(config['mtu']) < min_mtu:
            interface = config['ifname']
            error_msg = f'IPv6 address will be configured on interface "{interface}",\n' \
                        f'the required minimum MTU is {min_mtu}!'

            if 'address' in config:
                for address in config['address']:
                    if address in ['dhcpv6'] or is_ipv6(address):
                        raise ConfigError(error_msg)

            tmp = dict_search('ipv6.address.no_default_link_local', config)
            if tmp == None: raise ConfigError('link-local ' + error_msg)

            tmp = dict_search('ipv6.address.autoconf', config)
            if tmp != None: raise ConfigError(error_msg)

            tmp = dict_search('ipv6.address.eui64', config)
            if tmp != None: raise ConfigError(error_msg)

def verify_vrf(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation of VRF configuration.
    """
    from netifaces import interfaces
    if 'vrf' in config and config['vrf'] != 'default':
        if config['vrf'] not in interfaces():
            raise ConfigError('VRF "{vrf}" does not exist'.format(**config))

        if 'is_bridge_member' in config:
            raise ConfigError(
                'Interface "{ifname}" cannot be both a member of VRF "{vrf}" '
                'and bridge "{is_bridge_member}"!'.format(**config))

def verify_bond_bridge_member(config):
    """
    Checks if interface has a VRF configured and is also part of a bond or
    bridge, which is not allowed!
    """
    if 'vrf' in config:
        ifname = config['ifname']
        if 'is_bond_member' in config:
            raise ConfigError(f'Can not add interface "{ifname}" to bond, it has a VRF assigned!')
        if 'is_bridge_member' in config:
            raise ConfigError(f'Can not add interface "{ifname}" to bridge, it has a VRF assigned!')

def verify_tunnel(config):
    """
    This helper is used to verify the common part of the tunnel
    """
    from vyos.template import is_ipv4
    from vyos.template import is_ipv6

    if 'encapsulation' not in config:
        raise ConfigError('Must configure the tunnel encapsulation for '\
                          '{ifname}!'.format(**config))

    if 'source_address' not in config and 'source_interface' not in config:
        raise ConfigError('source-address or source-interface required for tunnel!')

    if 'remote' not in config and config['encapsulation'] != 'gre':
        raise ConfigError('remote ip address is mandatory for tunnel')

    if config['encapsulation'] in ['ipip6', 'ip6ip6', 'ip6gre', 'ip6gretap', 'ip6erspan']:
        error_ipv6 = 'Encapsulation mode requires IPv6'
        if 'source_address' in config and not is_ipv6(config['source_address']):
            raise ConfigError(f'{error_ipv6} source-address')

        if 'remote' in config and not is_ipv6(config['remote']):
            raise ConfigError(f'{error_ipv6} remote')
    else:
        error_ipv4 = 'Encapsulation mode requires IPv4'
        if 'source_address' in config and not is_ipv4(config['source_address']):
            raise ConfigError(f'{error_ipv4} source-address')

        if 'remote' in config and not is_ipv4(config['remote']):
            raise ConfigError(f'{error_ipv4} remote address')

    if config['encapsulation'] in ['sit', 'gretap', 'ip6gretap']:
        if 'source_interface' in config:
            encapsulation = config['encapsulation']
            raise ConfigError(f'Option source-interface can not be used with ' \
                              f'encapsulation "{encapsulation}"!')
    elif config['encapsulation'] == 'gre':
        if 'source_address' in config and is_ipv6(config['source_address']):
            raise ConfigError('Can not use local IPv6 address is for mGRE tunnels')

def verify_eapol(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation of EAPoL configuration.
    """
    if 'eapol' in config:
        if 'certificate' not in config['eapol']:
            raise ConfigError('Certificate must be specified when using EAPoL!')

        if 'pki' not in config or 'certificate' not in config['pki']:
            raise ConfigError('Invalid certificate specified for EAPoL')

        cert_name = config['eapol']['certificate']
        if cert_name not in config['pki']['certificate']:
            raise ConfigError('Invalid certificate specified for EAPoL')

        cert = config['pki']['certificate'][cert_name]

        if 'certificate' not in cert or 'private' not in cert or 'key' not in cert['private']:
            raise ConfigError('Invalid certificate/private key specified for EAPoL')

        if 'password_protected' in cert['private']:
            raise ConfigError('Encrypted private key cannot be used for EAPoL')

        if 'ca_certificate' in config['eapol']:
            if 'ca' not in config['pki']:
                raise ConfigError('Invalid CA certificate specified for EAPoL')

            ca_cert_name = config['eapol']['ca_certificate']

            if ca_cert_name not in config['pki']['ca']:
                raise ConfigError('Invalid CA certificate specified for EAPoL')

            ca_cert = config['pki']['ca'][ca_cert_name]

            if 'certificate' not in ca_cert:
                raise ConfigError('Invalid CA certificate specified for EAPoL')

def verify_mirror_redirect(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation of mirror and redirect interface configuration via tc(8)

    It makes no sense to mirror traffic back at yourself!
    """
    import os
    if {'mirror', 'redirect'} <= set(config):
        raise ConfigError('Mirror and redirect can not be enabled at the same time!')

    if 'mirror' in config:
        for direction, mirror_interface in config['mirror'].items():
            if not os.path.exists(f'/sys/class/net/{mirror_interface}'):
                raise ConfigError(f'Requested mirror interface "{mirror_interface}" '\
                                   'does not exist!')

            if mirror_interface == config['ifname']:
                raise ConfigError(f'Can not mirror "{direction}" traffic back '\
                                   'the originating interface!')

    if 'redirect' in config:
        redirect_ifname = config['redirect']
        if not os.path.exists(f'/sys/class/net/{redirect_ifname}'):
            raise ConfigError(f'Requested redirect interface "{redirect_ifname}" '\
                               'does not exist!')

    if ('mirror' in config or 'redirect' in config) and dict_search('traffic_policy.in', config) is not None:
        # XXX: support combination of limiting and redirect/mirror - this is an
        # artificial limitation
        raise ConfigError('Can not use ingress policy together with mirror or redirect!')

def verify_authentication(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation of authentication for either PPPoE or WWAN interfaces.

    If authentication CLI option is defined, both username and password must
    be set!
    """
    if 'authentication' not in config:
        return
    if not {'user', 'password'} <= set(config['authentication']):
        raise ConfigError('Authentication requires both username and ' \
                          'password to be set!')

def verify_address(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation of IP address assignment when interface is part
    of a bridge or bond.
    """
    if {'is_bridge_member', 'address'} <= set(config):
        interface = config['ifname']
        bridge_name = next(iter(config['is_bridge_member']))
        raise ConfigError(f'Cannot assign address to interface "{interface}" '
                          f'as it is a member of bridge "{bridge_name}"!')

def verify_bridge_delete(config):
    """
    Common helper function used by interface implementations to
    perform recurring validation of IP address assignmenr
    when interface also is part of a bridge.
    """
    if 'is_bridge_member' in config:
        interface = config['ifname']
        bridge_name = next(iter(config['is_bridge_member']))
        raise ConfigError(f'Interface "{interface}" cannot be deleted as it '
                          f'is a member of bridge "{bridge_name}"!')

def verify_interface_exists(ifname):
    """
    Common helper function used by interface implementations to perform
    recurring validation if an interface actually exists.
    """
    import os
    if not os.path.exists(f'/sys/class/net/{ifname}'):
        raise ConfigError(f'Interface "{ifname}" does not exist!')

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

    src_ifname = config['source_interface']
    if 'source_interface_is_bridge_member' in config:
        bridge_name = next(iter(config['source_interface_is_bridge_member']))
        raise ConfigError(f'Invalid source-interface "{src_ifname}". Interface '
                          f'is already a member of bridge "{bridge_name}"!')

    if 'source_interface_is_bond_member' in config:
        bond_name = next(iter(config['source_interface_is_bond_member']))
        raise ConfigError(f'Invalid source-interface "{src_ifname}". Interface '
                          f'is already a member of bond "{bond_name}"!')

    if 'is_source_interface' in config:
        tmp = config['is_source_interface']
        src_ifname = config['source_interface']
        raise ConfigError(f'Can not use source-interface "{src_ifname}", it already ' \
                          f'belongs to interface "{tmp}"!')

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
            interfaces = dict_search(f'dhcpv6_options.pd.{pd}.interface', config)

            if not interfaces:
                raise ConfigError('DHCPv6-PD requires an interface where to assign '
                                  'the delegated prefix!')

            for count, interface in enumerate(interfaces):
                if 'sla_id' in interfaces[interface]:
                    sla_ids.append(interfaces[interface]['sla_id'])
                else:
                    sla_ids.append(str(count))

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

    # VLAN and Q-in-Q IDs are not allowed to overlap
    if 'vif' in config and 'vif_s' in config:
        duplicate = list(set(config['vif']) & set(config['vif_s']))
        if duplicate:
            raise ConfigError(f'Duplicate VLAN id "{duplicate[0]}" used for vif and vif-s interfaces!')

    parent_ifname = config['ifname']
    # 802.1q VLANs
    for vlan_id in config.get('vif', {}):
        vlan = config['vif'][vlan_id]
        vlan['ifname'] = f'{parent_ifname}.{vlan_id}'

        verify_dhcpv6(vlan)
        verify_address(vlan)
        verify_vrf(vlan)
        verify_mirror_redirect(vlan)
        verify_mtu_parent(vlan, config)

    # 802.1ad (Q-in-Q) VLANs
    for s_vlan_id in config.get('vif_s', {}):
        s_vlan = config['vif_s'][s_vlan_id]
        s_vlan['ifname'] = f'{parent_ifname}.{s_vlan_id}'

        verify_dhcpv6(s_vlan)
        verify_address(s_vlan)
        verify_vrf(s_vlan)
        verify_mirror_redirect(s_vlan)
        verify_mtu_parent(s_vlan, config)

        for c_vlan_id in s_vlan.get('vif_c', {}):
            c_vlan = s_vlan['vif_c'][c_vlan_id]
            c_vlan['ifname'] = f'{parent_ifname}.{s_vlan_id}.{c_vlan_id}'

            verify_dhcpv6(c_vlan)
            verify_address(c_vlan)
            verify_vrf(c_vlan)
            verify_mirror_redirect(c_vlan)
            verify_mtu_parent(c_vlan, config)
            verify_mtu_parent(c_vlan, s_vlan)

def verify_accel_ppp_base_service(config, local_users=True):
    """
    Common helper function which must be used by all Accel-PPP services based
    on get_config_dict()
    """
    # vertify auth settings
    if local_users and dict_search('authentication.mode', config) == 'local':
        if dict_search(f'authentication.local_users', config) == None:
            raise ConfigError('Authentication mode local requires local users to be configured!')

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
        raise ConfigError('Server requires gateway-address to be configured!')

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

def verify_diffie_hellman_length(file, min_keysize):
    """ Verify Diffie-Hellamn keypair length given via file. It must be greater
    then or equal to min_keysize """
    import os
    import re
    from vyos.util import cmd

    try:
        keysize = str(min_keysize)
    except:
        return False

    if os.path.exists(file):
        out = cmd(f'openssl dhparam -inform PEM -in {file} -text')
        prog = re.compile('\d+\s+bit')
        if prog.search(out):
            bits = prog.search(out)[0].split()[0]
            if int(bits) >= int(min_keysize):
                return True

    return False

def verify_common_route_maps(config):
    """
    Common helper function used by routing protocol implementations to perform
    recurring validation if the specified route-map for either zebra to kernel
    installation exists (this is the top-level route_map key) or when a route
    is redistributed with a route-map that it exists!
    """
    # XXX: This function is called in combination with a previous call to:
    # tmp = conf.get_config_dict(['policy']) - see protocols_ospf.py as example.
    # We should NOT call this with the key_mangling option as this would rename
    # route-map hypens '-' to underscores '_' and one could no longer distinguish
    # what should have been the "proper" route-map name, as foo-bar and foo_bar
    # are two entire different route-map instances!
    for route_map in ['route-map', 'route_map']:
        if route_map not in config:
            continue
        tmp = config[route_map]
        # Check if the specified route-map exists, if not error out
        if dict_search(f'policy.route-map.{tmp}', config) == None:
            raise ConfigError(f'Specified route-map "{tmp}" does not exist!')

    if 'redistribute' in config:
        for protocol, protocol_config in config['redistribute'].items():
            if 'route_map' in protocol_config:
                verify_route_map(protocol_config['route_map'], config)

def verify_route_map(route_map_name, config):
    """
    Common helper function used by routing protocol implementations to perform
    recurring validation if a specified route-map exists!
    """
    # Check if the specified route-map exists, if not error out
    if dict_search(f'policy.route-map.{route_map_name}', config) == None:
        raise ConfigError(f'Specified route-map "{route_map_name}" does not exist!')

def verify_prefix_list(prefix_list, config, version=''):
    """
    Common helper function used by routing protocol implementations to perform
    recurring validation if a specified prefix-list exists!
    """
    # Check if the specified prefix-list exists, if not error out
    if dict_search(f'policy.prefix-list{version}.{prefix_list}', config) == None:
        raise ConfigError(f'Specified prefix-list{version} "{prefix_list}" does not exist!')

def verify_access_list(access_list, config, version=''):
    """
    Common helper function used by routing protocol implementations to perform
    recurring validation if a specified prefix-list exists!
    """
    # Check if the specified ACL exists, if not error out
    if dict_search(f'policy.access-list{version}.{access_list}', config) == None:
        raise ConfigError(f'Specified access-list{version} "{access_list}" does not exist!')
