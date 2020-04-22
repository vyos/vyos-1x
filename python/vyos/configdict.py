# Copyright 2019 VyOS maintainers and contributors <maintainers@vyos.io>
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

"""
A library for retrieving value dicts from VyOS configs in a declarative fashion.

"""

from vyos import ConfigError

def retrieve_config(path_hash, base_path, config):
    """
    Retrieves a VyOS config as a dict according to a declarative description

    The description dict, passed in the first argument, must follow this format:
    ``field_name : <path, type, [inner_options_dict]>``.

    Supported types are: ``str`` (for normal nodes),
    ``list`` (returns a list of strings, for multi nodes),
    ``bool`` (returns True if valueless node exists),
    ``dict`` (for tag nodes, returns a dict indexed by node names,
    according to description in the third item of the tuple).

    Args:
        path_hash (dict): Declarative description of the config to retrieve
        base_path (list): A base path to prepend to all option paths
        config (vyos.config.Config): A VyOS config object

    Returns:
        dict: config dict
    """
    config_hash = {}

    for k in path_hash:

        if type(path_hash[k]) != tuple:
            raise ValueError("In field {0}: expected a tuple, got a value {1}".format(k, str(path_hash[k])))
        if len(path_hash[k]) < 2:
            raise ValueError("In field {0}: field description must be a tuple of at least two items, path (list) and type".format(k))

        path = path_hash[k][0]
        if type(path) != list:
            raise ValueError("In field {0}: path must be a list, not a {1}".format(k, type(path)))

        typ = path_hash[k][1]
        if type(typ) != type:
            raise ValueError("In field {0}: type must be a type, not a {1}".format(k, type(typ)))

        path = base_path + path

        path_str = " ".join(path)

        if typ == str:
            config_hash[k] = config.return_value(path_str)
        elif typ == list:
            config_hash[k] = config.return_values(path_str)
        elif typ == bool:
            config_hash[k] = config.exists(path_str)
        elif typ == dict:
            try:
                inner_hash = path_hash[k][2]
            except IndexError:
                raise ValueError("The type of the \'{0}\' field is dict, but inner options hash is missing from the tuple".format(k))
            config_hash[k] = {}
            nodes = config.list_nodes(path_str)
            for node in nodes:
                config_hash[k][node] = retrieve_config(inner_hash, path + [node], config)

    return config_hash


def list_diff(first, second):
    """
    Diff two dictionaries and return only unique items
    """
    second = set(second)
    return [item for item in first if item not in second]


def get_ethertype(ethertype_val):
    if ethertype_val == '0x88A8':
        return '802.1ad'
    elif ethertype_val == '0x8100':
        return '802.1q'
    else:
        raise ConfigError('invalid ethertype "{}"'.format(ethertype_val))


def vlan_to_dict(conf):
    """
    Common used function which will extract VLAN related information from config
    and represent the result as Python dictionary.

    Function call's itself recursively if a vif-s/vif-c pair is detected.
    """
    vlan = {
        'id': conf.get_level()[-1], # get the '100' in 'interfaces bonding bond0 vif-s 100'
        'address': [],
        'address_remove': [],
        'description': '',
        'dhcp_client_id': '',
        'dhcp_hostname': '',
        'dhcp_vendor_class_id': '',
        'dhcpv6_prm_only': False,
        'dhcpv6_temporary': False,
        'disable': False,
        'disable_link_detect': 1,
        'egress_qos': '',
        'egress_qos_changed': False,
        'ip_disable_arp_filter': 1,
        'ip_enable_arp_accept': 0,
        'ip_enable_arp_announce': 0,
        'ip_enable_arp_ignore': 0,
        'ip_proxy_arp': 0,
        'ipv6_autoconf': 0,
        'ipv6_eui64_prefix': [],
        'ipv6_eui64_prefix_remove': [],
        'ipv6_forwarding': 1,
        'ipv6_dup_addr_detect': 1,
        'ingress_qos': '',
        'ingress_qos_changed': False,
        'mac': '',
        'mtu': 1500,
        'vrf': ''
    }
    # retrieve configured interface addresses
    if conf.exists('address'):
        vlan['address'] = conf.return_values('address')

    # Determine interface addresses (currently effective) - to determine which
    # address is no longer valid and needs to be removed from the bond
    eff_addr = conf.return_effective_values('address')
    act_addr = conf.return_values('address')
    vlan['address_remove'] = list_diff(eff_addr, act_addr)

    # retrieve interface description
    if conf.exists('description'):
        vlan['description'] = conf.return_value('description')

    # get DHCP client identifier
    if conf.exists('dhcp-options client-id'):
        vlan['dhcp_client_id'] = conf.return_value('dhcp-options client-id')

    # DHCP client host name (overrides the system host name)
    if conf.exists('dhcp-options host-name'):
        vlan['dhcp_hostname'] = conf.return_value('dhcp-options host-name')

    # DHCP client vendor identifier
    if conf.exists('dhcp-options vendor-class-id'):
        vlan['dhcp_vendor_class_id'] = conf.return_value('dhcp-options vendor-class-id')

    # DHCPv6 only acquire config parameters, no address
    if conf.exists('dhcpv6-options parameters-only'):
        vlan['dhcpv6_prm_only'] = True

    # DHCPv6 temporary IPv6 address
    if conf.exists('dhcpv6-options temporary'):
        vlan['dhcpv6_temporary'] = True

    # ignore link state changes
    if conf.exists('disable-link-detect'):
        vlan['disable_link_detect'] = 2

    # disable VLAN interface
    if conf.exists('disable'):
        vlan['disable'] = True

    # ARP filter configuration
    if conf.exists('ip disable-arp-filter'):
        vlan['ip_disable_arp_filter'] = 0

    # ARP enable accept
    if conf.exists('ip enable-arp-accept'):
        vlan['ip_enable_arp_accept'] = 1

    # ARP enable announce
    if conf.exists('ip enable-arp-announce'):
        vlan['ip_enable_arp_announce'] = 1

    # ARP enable ignore
    if conf.exists('ip enable-arp-ignore'):
        vlan['ip_enable_arp_ignore'] = 1

    # Enable Proxy ARP
    if conf.exists('ip enable-proxy-arp'):
        vlan['ip_proxy_arp'] = 1

    # Enable acquisition of IPv6 address using stateless autoconfig (SLAAC)
    if conf.exists('ipv6 address autoconf'):
        vlan['ipv6_autoconf'] = 1

    # Get prefix for IPv6 addressing based on MAC address (EUI-64)
    if conf.exists('ipv6 address eui64'):
        vlan['ipv6_eui64_prefix'].append(conf.return_value('ipv6 address eui64'))

    # Determine currently effective EUI64 address - to determine which
    # address is no longer valid and needs to be removed
    eff_addr = conf.return_effective_value('ipv6 address eui64')
    if eff_addr and eff_addr not in vlan['ipv6_eui64_prefix']:
        vlan['ipv6_eui64_prefix_remove'].append(eff_addr)

    # Disable IPv6 forwarding on this interface
    if conf.exists('ipv6 disable-forwarding'):
        vlan['ipv6_forwarding'] = 0

    # IPv6 Duplicate Address Detection (DAD) tries
    if conf.exists('ipv6 dup-addr-detect-transmits'):
        vlan['ipv6_dup_addr_detect'] = int(conf.return_value('ipv6 dup-addr-detect-transmits'))

    # Media Access Control (MAC) address
    if conf.exists('mac'):
        vlan['mac'] = conf.return_value('mac')

    # Maximum Transmission Unit (MTU)
    if conf.exists('mtu'):
        vlan['mtu'] = int(conf.return_value('mtu'))

    # retrieve VRF instance
    if conf.exists('vrf'):
        vlan['vrf'] = conf.return_value('vrf')

    # VLAN egress QoS
    if conf.exists('egress-qos'):
        vlan['egress_qos'] = conf.return_value('egress-qos')

    # egress changes QoS require VLAN interface recreation
    if conf.return_effective_value('egress-qos'):
        if vlan['egress_qos'] != conf.return_effective_value('egress-qos'):
            vlan['egress_qos_changed'] = True

    # VLAN ingress QoS
    if conf.exists('ingress-qos'):
        vlan['ingress_qos'] = conf.return_value('ingress-qos')

    # ingress changes QoS require VLAN interface recreation
    if conf.return_effective_value('ingress-qos'):
        if vlan['ingress_qos'] != conf.return_effective_value('ingress-qos'):
            vlan['ingress_qos_changed'] = True

    # ethertype is mandatory on vif-s nodes and only exists here!
    # check if this is a vif-s node at all:
    if conf.get_level()[-2] == 'vif-s':
        vlan['vif_c'] = []
        vlan['vif_c_remove'] = []

        # ethertype uses a default of 0x88A8
        tmp = '0x88A8'
        if conf.exists('ethertype'):
             tmp = conf.return_value('ethertype')
        vlan['ethertype'] = get_ethertype(tmp)

        # get vif-c interfaces (currently effective) - to determine which vif-c
        # interface is no longer present and needs to be removed
        eff_intf = conf.list_effective_nodes('vif-c')
        act_intf = conf.list_nodes('vif-c')
        vlan['vif_c_remove'] = list_diff(eff_intf, act_intf)

        # check if there is a Q-in-Q vlan customer interface
        # and call this function recursively
        if conf.exists('vif-c'):
            cfg_level = conf.get_level()
            # add new key (vif-c) to dictionary
            for vif in conf.list_nodes('vif-c'):
                # set config level to vif interface
                conf.set_level(cfg_level + ['vif-c', vif])
                vlan['vif_c'].append(vlan_to_dict(conf))

    return vlan
