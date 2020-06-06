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

from enum import Enum
from copy import deepcopy

from vyos import ConfigError
from vyos.ifconfig import Interface
from vyos.validate import is_member
from vyos.util import ifname_from_config

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

dhcpv6_pd_default_data = {
    'dhcpv6_prm_only': False,
    'dhcpv6_temporary': False,
    'dhcpv6_pd_length': '',
    'dhcpv6_pd_interfaces': []
}

interface_default_data = {
    **dhcpv6_pd_default_data,
    'address': [],
    'address_remove': [],
    'description': '',
    'dhcp_client_id': '',
    'dhcp_hostname': '',
    'dhcp_vendor_class_id': '',
    'disable': False,
    'disable_link_detect': 1,
    'ip_disable_arp_filter': 1,
    'ip_enable_arp_accept': 0,
    'ip_enable_arp_announce': 0,
    'ip_enable_arp_ignore': 0,
    'ip_proxy_arp': 0,
    'ipv6_accept_ra': 1,
    'ipv6_autoconf': 0,
    'ipv6_eui64_prefix': [],
    'ipv6_eui64_prefix_remove': [],
    'ipv6_forwarding': 1,
    'ipv6_dup_addr_detect': 1,
    'is_bridge_member': False,
    'mac': '',
    'mtu': 1500,
    'vrf': ''
}

vlan_default = {
    **interface_default_data,
    'egress_qos': '',
    'egress_qos_changed': False,
    'ingress_qos': '',
    'ingress_qos_changed': False,
    'vif_c': {},
    'vif_c_remove': []
}

# see: https://docs.python.org/3/library/enum.html#functional-api
disable = Enum('disable','none was now both')

def disable_state(conf, check=[3,5,7]):
    """
    return if and how a particual section of the configuration is has disable'd
    using "disable" including if it was disabled by one of its parent.

    check: a list of the level we should check, here 7,5 and 3
          interfaces ethernet eth1 vif-s 1 vif-c 2 disable
          interfaces ethernet eth1 vif 1 disable
          interfaces ethernet eth1 disable

    it returns an enum (none, was, now, both)
    """

    # save where we are in the config
    current_level = conf.get_level()

    # logic to figure out if the interface (or one of it parent is disabled)
    eff_disable = False
    act_disable = False

    levels = check[:]
    working_level = current_level[:]

    while levels:
        position = len(working_level)
        if not position:
            break
        if position not in levels:
            working_level = working_level[:-1]
            continue

        levels.remove(position)
        conf.set_level(working_level)
        working_level = working_level[:-1]

        eff_disable = eff_disable or conf.exists_effective('disable')
        act_disable = act_disable or conf.exists('disable')

    conf.set_level(current_level)

    # how the disabling changed
    if eff_disable and act_disable:
        return disable.both
    if eff_disable and not eff_disable:
        return disable.was
    if not eff_disable and act_disable:
        return disable.now
    return disable.none


def intf_to_dict(conf, default):
    """
    Common used function which will extract VLAN related information from config
    and represent the result as Python dictionary.

    Function call's itself recursively if a vif-s/vif-c pair is detected.
    """

    intf = deepcopy(default)
    intf['intf'] = ifname_from_config(conf)

    # retrieve interface description
    if conf.exists(['description']):
        intf['description'] = conf.return_value(['description'])

    # get DHCP client identifier
    if conf.exists(['dhcp-options', 'client-id']):
        intf['dhcp_client_id'] = conf.return_value(['dhcp-options', 'client-id'])

    # DHCP client host name (overrides the system host name)
    if conf.exists(['dhcp-options', 'host-name']):
        intf['dhcp_hostname'] = conf.return_value(['dhcp-options', 'host-name'])

    # DHCP client vendor identifier
    if conf.exists(['dhcp-options', 'vendor-class-id']):
        intf['dhcp_vendor_class_id'] = conf.return_value(
            ['dhcp-options', 'vendor-class-id'])

    # DHCPv6 only acquire config parameters, no address
    if conf.exists(['dhcpv6-options', 'parameters-only']):
        intf['dhcpv6_prm_only'] = True

    # DHCPv6 prefix delegation (RFC3633)
    current_level = conf.get_level()
    if conf.exists(['dhcpv6-options', 'prefix-delegation']):
        dhcpv6_pd_path = current_level + ['dhcpv6-options', 'prefix-delegation']
        conf.set_level(dhcpv6_pd_path)

        # retriebe DHCPv6-PD prefix helper length as some ISPs only hand out a
        # /64 by default (https://phabricator.vyos.net/T2506)
        if conf.exists(['length']):
            intf['dhcpv6_pd_length'] = conf.return_value(['length'])

        for interface in conf.list_nodes(['interface']):
            conf.set_level(dhcpv6_pd_path + ['interface', interface])
            pd = {
                'ifname': interface,
                'sla_id': '',
                'sla_len': '',
                'if_id': ''
            }

            if conf.exists(['sla-id']):
                pd['sla_id'] = conf.return_value(['sla-id'])

            if conf.exists(['sla-len']):
                pd['sla_len'] = conf.return_value(['sla-len'])

            if conf.exists(['address']):
                pd['if_id'] = conf.return_value(['address'])

            intf['dhcpv6_pd_interfaces'].append(pd)

    # re-set config level
    conf.set_level(current_level)

    # DHCPv6 temporary IPv6 address
    if conf.exists(['dhcpv6-options', 'temporary']):
        intf['dhcpv6_temporary'] = True

    # ignore link state changes
    if conf.exists(['disable-link-detect']):
        intf['disable_link_detect'] = 2

    # ARP filter configuration
    if conf.exists(['ip', 'disable-arp-filter']):
        intf['ip_disable_arp_filter'] = 0

    # ARP enable accept
    if conf.exists(['ip', 'enable-arp-accept']):
        intf['ip_enable_arp_accept'] = 1

    # ARP enable announce
    if conf.exists(['ip', 'enable-arp-announce']):
        intf['ip_enable_arp_announce'] = 1

    # ARP enable ignore
    if conf.exists(['ip', 'enable-arp-ignore']):
        intf['ip_enable_arp_ignore'] = 1

    # Enable Proxy ARP
    if conf.exists(['ip', 'enable-proxy-arp']):
        intf['ip_proxy_arp'] = 1

    # Enable acquisition of IPv6 address using stateless autoconfig (SLAAC)
    if conf.exists(['ipv6', 'address', 'autoconf']):
        intf['ipv6_autoconf'] = 1

    # Disable IPv6 forwarding on this interface
    if conf.exists(['ipv6', 'disable-forwarding']):
        intf['ipv6_forwarding'] = 0

    # check if interface is member of a bridge
    intf['is_bridge_member'] = is_member(conf, intf['intf'], 'bridge')

    # IPv6 Duplicate Address Detection (DAD) tries
    if conf.exists(['ipv6', 'dup-addr-detect-transmits']):
        intf['ipv6_dup_addr_detect'] = int(
            conf.return_value(['ipv6', 'dup-addr-detect-transmits']))

    # Media Access Control (MAC) address
    if conf.exists(['mac']):
        intf['mac'] = conf.return_value(['mac'])

    # Maximum Transmission Unit (MTU)
    if conf.exists(['mtu']):
        intf['mtu'] = int(conf.return_value(['mtu']))

    # retrieve VRF instance
    if conf.exists(['vrf']):
        intf['vrf'] = conf.return_value(['vrf'])

    #  egress QoS
    if conf.exists(['egress-qos']):
        intf['egress_qos'] = conf.return_value(['egress-qos'])

    # egress changes QoS require VLAN interface recreation
    if conf.return_effective_value(['egress-qos']):
        if intf['egress_qos'] != conf.return_effective_value(['egress-qos']):
            intf['egress_qos_changed'] = True

    # ingress QoS
    if conf.exists(['ingress-qos']):
        intf['ingress_qos'] = conf.return_value(['ingress-qos'])

    # ingress changes QoS require VLAN interface recreation
    if conf.return_effective_value(['ingress-qos']):
        if intf['ingress_qos'] != conf.return_effective_value(['ingress-qos']):
            intf['ingress_qos_changed'] = True

    # Get the interface addresses
    intf['address'] = conf.return_values(['address'])

    # addresses to remove - difference between effective and working config
    intf['address_remove'] = list_diff(
            conf.return_effective_values(['address']), intf['address'])

    # Get prefixes for IPv6 addressing based on MAC address (EUI-64)
    intf['ipv6_eui64_prefix'] = conf.return_values(['ipv6', 'address', 'eui64'])

    # EUI64 to remove - difference between effective and working config
    intf['ipv6_eui64_prefix_remove'] = list_diff(
            conf.return_effective_values(['ipv6', 'address', 'eui64']),
            intf['ipv6_eui64_prefix'])

    # Determine if the interface should be disabled
    disabled = disable_state(conf)
    if disabled == disable.both:
        # was and is still disabled
        intf['disable'] = True
    elif disabled == disable.now:
        # it is now disable but was not before
        intf['disable'] = True
    elif disabled == disable.was:
        # it was disable but not anymore
        intf['disable'] = False
    else:
        # normal change
        intf['disable'] = False

    # Remove the default link-local address if no-default-link-local is set,
    # if member of a bridge or if disabled (it may not have a MAC if it's down)
    if ( conf.exists(['ipv6', 'address', 'no-default-link-local'])
            or intf.get('is_bridge_member') or intf['disable'] ):
        intf['ipv6_eui64_prefix_remove'].append('fe80::/64')
    else:
        # add the link-local by default to make IPv6 work
        intf['ipv6_eui64_prefix'].append('fe80::/64')

    # If MAC has changed, remove and re-add all IPv6 EUI64 addresses
    try:
        interface = Interface(intf['intf'], create=False)
        if intf['mac'] and intf['mac'] != interface.get_mac():
            intf['ipv6_eui64_prefix_remove'] += intf['ipv6_eui64_prefix']
    except Exception:
        # If the interface does not exist, it could not have changed
        pass

    # to make IPv6 SLAAC and DHCPv6 work with forwarding=1,
    # accept_ra must be 2
    if intf['ipv6_autoconf'] or 'dhcpv6' in intf['address']:
        intf['ipv6_accept_ra'] = 2

    return intf, disable



def add_to_dict(conf, disabled, ifdict, section, key):
    """
    parse a section of vif/vif-s/vif-c and add them to the dict
    follow the convention to:
    * use the "key" for what to add
    * use the "key" what what to remove

    conf:     is the Config() already at the level we need to parse
    disabled: is a disable enum so we know how to handle to data
    intf:     if the interface dictionary
    section:  is the section name to parse (vif/vif-s/vif-c)
    key:      is the dict key to use (vif/vifs/vifc)
    """

    if not conf.exists(section):
        return ifdict

    effect = conf.list_effective_nodes(section)
    active = conf.list_nodes(section)

    # the section to parse for vlan
    sections = []

    # determine which interfaces to add or remove based on disable state
    if disabled == disable.both:
        # was and is still disabled
        ifdict[f'{key}_remove'] = []
    elif disabled == disable.now:
        # it is now disable but was not before
        ifdict[f'{key}_remove'] = effect
    elif disabled == disable.was:
        # it was disable but not anymore
        ifdict[f'{key}_remove'] = []
        sections = active
    else:
        # normal change
        # get interfaces (currently effective) - to determine which
        # interface is no longer present and needs to be removed
        ifdict[f'{key}_remove'] = list_diff(effect, active)
        sections = active

    current_level = conf.get_level()

    # add each section, the key must already exists
    for s in sections:
        # set config level to vif interface
        conf.set_level(current_level + [section, s])
        # add the vlan config as a key (vlan id) - value (config) pair
        ifdict[key][s] = vlan_to_dict(conf)

    # re-set configuration level to leave things as found
    conf.set_level(current_level)

    return ifdict


def vlan_to_dict(conf, default=vlan_default):
    vlan, disabled = intf_to_dict(conf, default)

    # if this is a not within vif-s node, we are done
    if conf.get_level()[-2] != 'vif-s':
        return vlan

    # ethertype is mandatory on vif-s nodes and only exists here!
    # ethertype uses a default of 0x88A8
    tmp = '0x88A8'
    if conf.exists('ethertype'):
        tmp = conf.return_value('ethertype')
    vlan['ethertype'] = get_ethertype(tmp)

    # check if there is a Q-in-Q vlan customer interface
    # and call this function recursively
    add_to_dict(conf, disable, vlan, 'vif-c', 'vif_c')

    return vlan
