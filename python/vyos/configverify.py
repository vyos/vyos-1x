# Copyright 2020-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.utils.dict import dict_search
# pattern re-used in ipsec migration script
dynamic_interface_pattern = r'(ppp|pppoe|sstpc|l2tp|ipoe)[0-9]+'

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
        # Not all interfaces support min/max MTU
        # https://vyos.dev/T5011
        try:
            min_mtu = tmp.get_min_mtu()
            max_mtu = tmp.get_max_mtu()
        except: # Fallback to defaults
            min_mtu = 68
            max_mtu = 9000

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
        raise ConfigError(f'Interface MTU "{mtu}" too high, ' \
                          f'parent interface MTU is "{parent_mtu}"!')

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
                        f'the required minimum MTU is "{min_mtu}"!'

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
    from vyos.utils.network import interface_exists
    if 'vrf' in config:
        vrfs = config['vrf']
        if isinstance(vrfs, str):
            vrfs = [vrfs]

        for vrf in vrfs:
            if vrf == 'default':
                continue
            if not interface_exists(vrf):
                raise ConfigError(f'VRF "{vrf}" does not exist!')

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

def verify_mirror_redirect(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation of mirror and redirect interface configuration via tc(8)

    It makes no sense to mirror traffic back at yourself!
    """
    from vyos.utils.network import interface_exists
    if {'mirror', 'redirect'} <= set(config):
        raise ConfigError('Mirror and redirect can not be enabled at the same time!')

    if 'mirror' in config:
        for direction, mirror_interface in config['mirror'].items():
            if not interface_exists(mirror_interface):
                raise ConfigError(f'Requested mirror interface "{mirror_interface}" '\
                                   'does not exist!')

            if mirror_interface == config['ifname']:
                raise ConfigError(f'Can not mirror "{direction}" traffic back '\
                                   'the originating interface!')

    if 'redirect' in config:
        redirect_ifname = config['redirect']
        if not interface_exists(redirect_ifname):
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
    if not {'username', 'password'} <= set(config['authentication']):
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

def verify_interface_exists(ifname, warning_only=False):
    """
    Common helper function used by interface implementations to perform
    recurring validation if an interface actually exists. We first probe
    if the interface is defined on the CLI, if it's not found we try if
    it exists at the OS level.
    """
    from vyos.base import Warning
    from vyos.configquery import ConfigTreeQuery
    from vyos.utils.dict import dict_search_recursive
    from vyos.utils.network import interface_exists

    # Check if interface is present in CLI config
    config = ConfigTreeQuery()
    tmp = config.get_config_dict(['interfaces'], get_first_key=True)
    if bool(list(dict_search_recursive(tmp, ifname))):
        return True

    # Interface not found on CLI, try Linux Kernel
    if interface_exists(ifname):
        return True

    message = f'Interface "{ifname}" does not exist!'
    if warning_only:
        Warning(message)
        return False
    raise ConfigError(message)

def verify_source_interface(config):
    """
    Common helper function used by interface implementations to
    perform recurring validation of the existence of a source-interface
    required by e.g. peth/MACvlan, MACsec ...
    """
    import re
    from vyos.utils.network import interface_exists

    ifname = config['ifname']
    if 'source_interface' not in config:
        raise ConfigError(f'Physical source-interface required for "{ifname}"!')

    src_ifname = config['source_interface']
    # We do not allow sourcing other interfaces (e.g. tunnel) from dynamic interfaces
    tmp = re.compile(dynamic_interface_pattern)
    if tmp.match(src_ifname):
        raise ConfigError(f'Can not source "{ifname}" from dynamic interface "{src_ifname}"!')

    if not interface_exists(src_ifname):
        raise ConfigError(f'Specified source-interface {src_ifname} does not exist')

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
        raise ConfigError(f'Can not use source-interface "{src_ifname}", it already ' \
                          f'belongs to interface "{tmp}"!')

def verify_dhcpv6(config):
    """
    Common helper function used by interface implementations to perform
    recurring validation of DHCPv6 options which are mutually exclusive.
    """
    if 'dhcpv6_options' in config:
        if {'parameters_only', 'temporary'} <= set(config['dhcpv6_options']):
            raise ConfigError('DHCPv6 temporary and parameters-only options '
                              'are mutually exclusive!')

        # It is not allowed to have duplicate SLA-IDs as those identify an
        # assigned IPv6 subnet from a delegated prefix
        for pd in (dict_search('dhcpv6_options.pd', config) or []):
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


def verify_diffie_hellman_length(file, min_keysize):
    """ Verify Diffie-Hellamn keypair length given via file. It must be greater
    then or equal to min_keysize """
    import os
    import re
    from vyos.utils.process import cmd

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

def verify_pki_certificate(config: dict, cert_name: str, no_password_protected: bool=False):
    """
    Common helper function user by PKI consumers to perform recurring
    validation functions for PEM based certificates
    """
    if 'pki' not in config:
        raise ConfigError('PKI is not configured!')

    if 'certificate' not in config['pki']:
        raise ConfigError('PKI does not contain any certificates!')

    if cert_name not in config['pki']['certificate']:
        raise ConfigError(f'Certificate "{cert_name}" not found in configuration!')

    pki_cert = config['pki']['certificate'][cert_name]
    if 'certificate' not in pki_cert:
        raise ConfigError(f'PEM certificate for "{cert_name}" missing in configuration!')

    if 'private' not in pki_cert or 'key' not in pki_cert['private']:
        raise ConfigError(f'PEM private key for "{cert_name}" missing in configuration!')

    if no_password_protected and 'password_protected' in pki_cert['private']:
        raise ConfigError('Password protected PEM private key is not supported!')

def verify_pki_ca_certificate(config: dict, ca_name: str):
    """
    Common helper function user by PKI consumers to perform recurring
    validation functions for PEM based CA certificates
    """
    if 'pki' not in config:
        raise ConfigError('PKI is not configured!')

    if 'ca' not in config['pki']:
        raise ConfigError('PKI does not contain any CA certificates!')

    if ca_name not in config['pki']['ca']:
        raise ConfigError(f'CA Certificate "{ca_name}" not found in configuration!')

    pki_cert = config['pki']['ca'][ca_name]
    if 'certificate' not in pki_cert:
        raise ConfigError(f'PEM CA certificate for "{cert_name}" missing in configuration!')

def verify_pki_dh_parameters(config: dict, dh_name: str, min_key_size: int=0):
    """
    Common helper function user by PKI consumers to perform recurring
    validation functions on DH parameters
    """
    from vyos.pki import load_dh_parameters

    if 'pki' not in config:
        raise ConfigError('PKI is not configured!')

    if 'dh' not in config['pki']:
        raise ConfigError('PKI does not contain any DH parameters!')

    if dh_name not in config['pki']['dh']:
        raise ConfigError(f'DH parameter "{dh_name}" not found in configuration!')

    if min_key_size:
        pki_dh = config['pki']['dh'][dh_name]
        dh_params = load_dh_parameters(pki_dh['parameters'])
        dh_numbers = dh_params.parameter_numbers()
        dh_bits = dh_numbers.p.bit_length()
        if dh_bits < min_key_size:
            raise ConfigError(f'Minimum DH key-size is {min_key_size} bits!')
