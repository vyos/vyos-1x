# Copyright 2019-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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
import os
import json

from vyos.utils.dict import dict_search
from vyos.utils.process import cmd

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


def dict_merge(source, destination):
    """ Merge two dictionaries. Only keys which are not present in destination
    will be copied from source, anything else will be kept untouched. Function
    will return a new dict which has the merged key/value pairs. """
    from copy import deepcopy
    tmp = deepcopy(destination)

    for key, value in source.items():
        if key not in tmp:
            tmp[key] = value
        elif isinstance(source[key], dict):
            tmp[key] = dict_merge(source[key], tmp[key])

    return tmp

def list_diff(first, second):
    """ Diff two dictionaries and return only unique items """
    second = set(second)
    return [item for item in first if item not in second]

def is_node_changed(conf, path):
   """
   Check if any key under path has been changed and return True.
   If nothing changed, return false
   """
   from vyos.configdiff import get_config_diff
   D = get_config_diff(conf, key_mangling=('-', '_'))
   return D.is_node_changed(path)

def leaf_node_changed(conf, path):
    """
    Check if a leaf node was altered. If it has been altered - values has been
    changed, or it was added/removed, we will return a list containing the old
    value(s). If nothing has been changed, None is returned.

    NOTE: path must use the real CLI node name (e.g. with a hyphen!)
    """
    from vyos.configdiff import get_config_diff
    D = get_config_diff(conf, key_mangling=('-', '_'))
    (new, old) = D.get_value_diff(path)
    if new != old:
        if isinstance(old, dict):
            # valueLess nodes return {} if node is deleted
            return True
        if old is None and isinstance(new, dict):
            # valueLess nodes return {} if node was added
            return True
        if old is None:
            return []
        if isinstance(old, str):
            return [old]
        if isinstance(old, list):
            if isinstance(new, str):
                new = [new]
            elif isinstance(new, type(None)):
                new = []
            return list_diff(old, new)

    return None

def node_changed(conf, path, key_mangling=None, recursive=False, expand_nodes=None) -> list:
    """
    Check if node under path (or anything under path if recursive=True) was changed. By default
    we only check if a node or subnode (recursive) was deleted from path. If expand_nodes
    is set to Diff.ADD we can also check if something was added to the path.

    If nothing changed, an empty list is returned.
    """
    from vyos.configdiff import get_config_diff
    from vyos.configdiff import Diff
    # to prevent circular dependencies we assign the default here
    if not expand_nodes: expand_nodes = Diff.DELETE
    D = get_config_diff(conf, key_mangling)
    # get_child_nodes_diff() will return dict_keys()
    tmp = D.get_child_nodes_diff(path, expand_nodes=expand_nodes, recursive=recursive)
    output = []
    if expand_nodes & Diff.DELETE:
        output.extend(list(tmp['delete'].keys()))
    if expand_nodes & Diff.ADD:
        output.extend(list(tmp['add'].keys()))

    # remove duplicate keys from list, this happens when a node (e.g. description) is altered
    output = list(dict.fromkeys(output))
    return output

def get_removed_vlans(conf, path, dict):
    """
    Common function to parse a dictionary retrieved via get_config_dict() and
    determine any added/removed VLAN interfaces - be it 802.1q or Q-in-Q.
    """
    from vyos.configdiff import get_config_diff, Diff

    # Check vif, vif-s/vif-c VLAN interfaces for removal
    D = get_config_diff(conf, key_mangling=('-', '_'))
    D.set_level(conf.get_level())

    # get_child_nodes() will return dict_keys(), mangle this into a list with PEP448
    keys = D.get_child_nodes_diff(path + ['vif'], expand_nodes=Diff.DELETE)['delete'].keys()
    if keys: dict['vif_remove'] = [*keys]

    # get_child_nodes() will return dict_keys(), mangle this into a list with PEP448
    keys = D.get_child_nodes_diff(path + ['vif-s'], expand_nodes=Diff.DELETE)['delete'].keys()
    if keys: dict['vif_s_remove'] = [*keys]

    for vif in dict.get('vif_s', {}).keys():
        keys = D.get_child_nodes_diff(path + ['vif-s', vif, 'vif-c'], expand_nodes=Diff.DELETE)['delete'].keys()
        if keys: dict['vif_s'][vif]['vif_c_remove'] = [*keys]

    return dict

def is_member(conf, interface, intftype=None):
    """
    Checks if passed interface is member of other interface of specified type.
    intftype is optional, if not passed it will search all known types
    (currently bridge and bonding)

    Returns: dict
    empty -> Interface is not a member
    key -> Interface is a member of this interface
    """
    ret_val = {}
    intftypes = ['bonding', 'bridge']

    if intftype not in intftypes + [None]:
        raise ValueError((
            f'unknown interface type "{intftype}" or it cannot '
            f'have member interfaces'))

    intftype = intftypes if intftype == None else [intftype]

    for iftype in intftype:
        base = ['interfaces', iftype]
        for intf in conf.list_nodes(base):
            member = base + [intf, 'member', 'interface', interface]
            if conf.exists(member):
                tmp = conf.get_config_dict(member, key_mangling=('-', '_'),
                                           get_first_key=True,
                                           no_tag_node_value_mangle=True)
                ret_val.update({intf : tmp})

    return ret_val

def is_mirror_intf(conf, interface, direction=None):
    """
    Check whether the passed interface is used for port mirroring. Direction
    is optional, if not passed it will search all known direction
    (currently ingress and egress)

    Returns:
    None -> Interface is not a monitor interface
    Array() -> This interface is a monitor interface of interfaces
    """
    from vyos.ifconfig import Section

    directions = ['ingress', 'egress']
    if direction not in directions + [None]:
        raise ValueError(f'Unknown interface mirror direction "{direction}"')

    direction = directions if direction == None else [direction]

    ret_val = None
    base = ['interfaces']

    for dir in direction:
        for iftype in conf.list_nodes(base):
            iftype_base = base + [iftype]
            for intf in conf.list_nodes(iftype_base):
                mirror = iftype_base + [intf, 'mirror', dir, interface]
                if conf.exists(mirror):
                    path = ['interfaces', Section.section(intf), intf]
                    tmp = conf.get_config_dict(path, key_mangling=('-', '_'),
                                               get_first_key=True)
                    ret_val = {intf : tmp}

    return ret_val

def has_address_configured(conf, intf):
    """
    Checks if interface has an address configured.
    Checks the following config nodes:
    'address', 'ipv6 address eui64', 'ipv6 address autoconf'

    Returns True if interface has address configured, False if it doesn't.
    """
    from vyos.ifconfig import Section
    ret = False

    old_level = conf.get_level()
    conf.set_level([])

    intfpath = ['interfaces', Section.get_config_path(intf)]
    if (conf.exists([intfpath, 'address']) or
        conf.exists([intfpath, 'ipv6', 'address', 'autoconf']) or
        conf.exists([intfpath, 'ipv6', 'address', 'eui64'])):
        ret = True

    conf.set_level(old_level)
    return ret

def has_vrf_configured(conf, intf):
    """
    Checks if interface has a VRF configured.

    Returns True if interface has VRF configured, False if it doesn't.
    """
    from vyos.ifconfig import Section
    ret = False

    old_level = conf.get_level()
    conf.set_level([])

    if conf.exists(['interfaces', Section.get_config_path(intf), 'vrf']):
        ret = True

    conf.set_level(old_level)
    return ret

def has_vlan_subinterface_configured(conf, intf):
    """
    Checks if interface has an VLAN subinterface configured.
    Checks the following config nodes:
    'vif', 'vif-s'

    Return True if interface has VLAN subinterface configured.
    """
    from vyos.ifconfig import Section
    ret = False

    intfpath = ['interfaces', Section.section(intf), intf]
    if (conf.exists(intfpath + ['vif']) or conf.exists(intfpath + ['vif-s'])):
        ret = True

    return ret

def is_source_interface(conf, interface, intftype=None):
    """
    Checks if passed interface is configured as source-interface of other
    interfaces of specified type. intftype is optional, if not passed it will
    search all known types (currently pppoe, macsec, pseudo-ethernet, tunnel
    and vxlan)

    Returns:
    None -> Interface is not a member
    interface name -> Interface is a member of this interface
    False -> interface type cannot have members
    """
    ret_val = None
    intftypes = ['macsec', 'pppoe', 'pseudo-ethernet', 'tunnel', 'vxlan']
    if not intftype:
        intftype = intftypes

    if isinstance(intftype, str):
        intftype = [intftype]
    elif not isinstance(intftype, list):
        raise ValueError(f'Interface type "{type(intftype)}" must be either str or list!')

    if not all(x in intftypes for x in intftype):
        raise ValueError(f'unknown interface type "{intftype}" or it can not '
            'have a source-interface')

    for it in intftype:
        base = ['interfaces', it]
        for intf in conf.list_nodes(base):
            src_intf = base + [intf, 'source-interface']
            if conf.exists(src_intf) and interface in conf.return_values(src_intf):
                ret_val = intf
                break

    return ret_val

def get_dhcp_interfaces(conf, vrf=None):
    """ Common helper functions to retrieve all interfaces from current CLI
    sessions that have DHCP configured. """
    dhcp_interfaces = {}
    dict = conf.get_config_dict(['interfaces'], get_first_key=True)
    if not dict:
        return dhcp_interfaces

    def check_dhcp(config):
        ifname = config['ifname']
        tmp = {}
        if 'address' in config and 'dhcp' in config['address']:
            options = {}
            if dict_search('dhcp_options.default_route_distance', config) != None:
                options.update({'dhcp_options' : config['dhcp_options']})
            if 'vrf' in config:
                if vrf == config['vrf']: tmp.update({ifname : options})
            else:
                if vrf is None: tmp.update({ifname : options})

        return tmp

    for section, interface in dict.items():
        for ifname in interface:
            # always reset config level, as get_interface_dict() will alter it
            conf.set_level([])
            # we already have a dict representation of the config from get_config_dict(),
            # but with the extended information from get_interface_dict() we also
            # get the DHCP client default-route-distance default option if not specified.
            _, ifconfig = get_interface_dict(conf, ['interfaces', section], ifname)

            tmp = check_dhcp(ifconfig)
            dhcp_interfaces.update(tmp)
            # check per VLAN interfaces
            for vif, vif_config in ifconfig.get('vif', {}).items():
                tmp = check_dhcp(vif_config)
                dhcp_interfaces.update(tmp)
            # check QinQ VLAN interfaces
            for vif_s, vif_s_config in ifconfig.get('vif_s', {}).items():
                tmp = check_dhcp(vif_s_config)
                dhcp_interfaces.update(tmp)
                for vif_c, vif_c_config in vif_s_config.get('vif_c', {}).items():
                    tmp = check_dhcp(vif_c_config)
                    dhcp_interfaces.update(tmp)

    return dhcp_interfaces

def get_pppoe_interfaces(conf, vrf=None):
    """ Common helper functions to retrieve all interfaces from current CLI
    sessions that have DHCP configured. """
    pppoe_interfaces = {}
    conf.set_level([])
    for ifname in conf.list_nodes(['interfaces', 'pppoe']):
        # always reset config level, as get_interface_dict() will alter it
        conf.set_level([])
        # we already have a dict representation of the config from get_config_dict(),
        # but with the extended information from get_interface_dict() we also
        # get the DHCP client default-route-distance default option if not specified.
        _, ifconfig = get_interface_dict(conf, ['interfaces', 'pppoe'], ifname)

        options = {}
        if 'default_route_distance' in ifconfig:
            options.update({'default_route_distance' : ifconfig['default_route_distance']})
        if 'no_default_route' in ifconfig:
            options.update({'no_default_route' : {}})
        if 'vrf' in ifconfig:
            if vrf == ifconfig['vrf']: pppoe_interfaces.update({ifname : options})
        else:
            if vrf is None: pppoe_interfaces.update({ifname : options})

    return pppoe_interfaces

def get_interface_dict(config, base, ifname='', recursive_defaults=True, with_pki=False):
    """
    Common utility function to retrieve and mangle the interfaces configuration
    from the CLI input nodes. All interfaces have a common base where value
    retrival is identical. This function must be used whenever possible when
    working on the interfaces node!

    Return a dictionary with the necessary interface config keys.
    """
    if not ifname:
        from vyos import ConfigError
        # determine tagNode instance
        if 'VYOS_TAGNODE_VALUE' not in os.environ:
            raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')
        ifname = os.environ['VYOS_TAGNODE_VALUE']

    # Check if interface has been removed. We must use exists() as
    # get_config_dict() will always return {} - even when an empty interface
    # node like the following exists.
    # +macsec macsec1 {
    # +}
    if not config.exists(base + [ifname]):
        dict = config.get_config_dict(base + [ifname], key_mangling=('-', '_'),
                                      get_first_key=True,
                                      no_tag_node_value_mangle=True)
        dict.update({'deleted' : {}})
    else:
        # Get config_dict with default values
        dict = config.get_config_dict(base + [ifname], key_mangling=('-', '_'),
                                      get_first_key=True,
                                      no_tag_node_value_mangle=True,
                                      with_defaults=True,
                                      with_recursive_defaults=recursive_defaults,
                                      with_pki=with_pki)

        # If interface does not request an IPv4 DHCP address there is no need
        # to keep the dhcp-options key
        if 'address' not in dict or 'dhcp' not in dict['address']:
            if 'dhcp_options' in dict:
                del dict['dhcp_options']

    # Add interface instance name into dictionary
    dict.update({'ifname': ifname})

    # Check if QoS policy applied on this interface - See ifconfig.interface.set_mirror_redirect()
    if config.exists(['qos', 'interface', ifname]):
        dict.update({'traffic_policy': {}})

    address = leaf_node_changed(config, base + [ifname, 'address'])
    if address: dict.update({'address_old' : address})

    # Check if we are a member of a bridge device
    bridge = is_member(config, ifname, 'bridge')
    if bridge: dict.update({'is_bridge_member' : bridge})

    # Check if it is a monitor interface
    mirror = is_mirror_intf(config, ifname)
    if mirror: dict.update({'is_mirror_intf' : mirror})

    # Check if we are a member of a bond device
    bond = is_member(config, ifname, 'bonding')
    if bond: dict.update({'is_bond_member' : bond})

    # Check if any DHCP options changed which require a client restat
    dhcp = is_node_changed(config, base + [ifname, 'dhcp-options'])
    if dhcp: dict.update({'dhcp_options_changed' : {}})

    # Changine interface VRF assignemnts require a DHCP restart, too
    dhcp = is_node_changed(config, base + [ifname, 'vrf'])
    if dhcp: dict.update({'dhcp_options_changed' : {}})

    # Some interfaces come with a source_interface which must also not be part
    # of any other bond or bridge interface as it is exclusivly assigned as the
    # Kernels "lower" interface to this new "virtual/upper" interface.
    if 'source_interface' in dict:
        # Check if source interface is member of another bridge
        tmp = is_member(config, dict['source_interface'], 'bridge')
        if tmp: dict.update({'source_interface_is_bridge_member' : tmp})

        # Check if source interface is member of another bridge
        tmp = is_member(config, dict['source_interface'], 'bonding')
        if tmp: dict.update({'source_interface_is_bond_member' : tmp})

    mac = leaf_node_changed(config, base + [ifname, 'mac'])
    if mac: dict.update({'mac_old' : mac})

    eui64 = leaf_node_changed(config, base + [ifname, 'ipv6', 'address', 'eui64'])
    if eui64:
        tmp = dict_search('ipv6.address', dict)
        if not tmp:
            dict.update({'ipv6': {'address': {'eui64_old': eui64}}})
        else:
            dict['ipv6']['address'].update({'eui64_old': eui64})

    for vif, vif_config in dict.get('vif', {}).items():
        # Add subinterface name to dictionary
        dict['vif'][vif].update({'ifname' : f'{ifname}.{vif}'})

        if config.exists(['qos', 'interface', f'{ifname}.{vif}']):
            dict['vif'][vif].update({'traffic_policy': {}})

        if 'deleted' not in dict:
            address = leaf_node_changed(config, base + [ifname, 'vif', vif, 'address'])
            if address: dict['vif'][vif].update({'address_old' : address})

            # If interface does not request an IPv4 DHCP address there is no need
            # to keep the dhcp-options key
            if 'address' not in dict['vif'][vif] or 'dhcp' not in dict['vif'][vif]['address']:
                if 'dhcp_options' in dict['vif'][vif]:
                    del dict['vif'][vif]['dhcp_options']

        # Check if we are a member of a bridge device
        bridge = is_member(config, f'{ifname}.{vif}', 'bridge')
        if bridge: dict['vif'][vif].update({'is_bridge_member' : bridge})

        # Check if any DHCP options changed which require a client restat
        dhcp = is_node_changed(config, base + [ifname, 'vif', vif, 'dhcp-options'])
        if dhcp: dict['vif'][vif].update({'dhcp_options_changed' : {}})

    for vif_s, vif_s_config in dict.get('vif_s', {}).items():
        # Add subinterface name to dictionary
        dict['vif_s'][vif_s].update({'ifname' : f'{ifname}.{vif_s}'})

        if config.exists(['qos', 'interface', f'{ifname}.{vif_s}']):
            dict['vif_s'][vif_s].update({'traffic_policy': {}})

        if 'deleted' not in dict:
            address = leaf_node_changed(config, base + [ifname, 'vif-s', vif_s, 'address'])
            if address: dict['vif_s'][vif_s].update({'address_old' : address})

            # If interface does not request an IPv4 DHCP address there is no need
            # to keep the dhcp-options key
            if 'address' not in dict['vif_s'][vif_s] or 'dhcp' not in \
                dict['vif_s'][vif_s]['address']:
                if 'dhcp_options' in dict['vif_s'][vif_s]:
                    del dict['vif_s'][vif_s]['dhcp_options']

        # Check if we are a member of a bridge device
        bridge = is_member(config, f'{ifname}.{vif_s}', 'bridge')
        if bridge: dict['vif_s'][vif_s].update({'is_bridge_member' : bridge})

        # Check if any DHCP options changed which require a client restat
        dhcp = is_node_changed(config, base + [ifname, 'vif-s', vif_s, 'dhcp-options'])
        if dhcp: dict['vif_s'][vif_s].update({'dhcp_options_changed' : {}})

        for vif_c, vif_c_config in vif_s_config.get('vif_c', {}).items():
            # Add subinterface name to dictionary
            dict['vif_s'][vif_s]['vif_c'][vif_c].update({'ifname' : f'{ifname}.{vif_s}.{vif_c}'})

            if config.exists(['qos', 'interface', f'{ifname}.{vif_s}.{vif_c}']):
                dict['vif_s'][vif_s]['vif_c'][vif_c].update({'traffic_policy': {}})

            if 'deleted' not in dict:
                address = leaf_node_changed(config, base + [ifname, 'vif-s', vif_s, 'vif-c', vif_c, 'address'])
                if address: dict['vif_s'][vif_s]['vif_c'][vif_c].update(
                        {'address_old' : address})

                # If interface does not request an IPv4 DHCP address there is no need
                # to keep the dhcp-options key
                if 'address' not in dict['vif_s'][vif_s]['vif_c'][vif_c] or 'dhcp' \
                    not in dict['vif_s'][vif_s]['vif_c'][vif_c]['address']:
                    if 'dhcp_options' in dict['vif_s'][vif_s]['vif_c'][vif_c]:
                        del dict['vif_s'][vif_s]['vif_c'][vif_c]['dhcp_options']

            # Check if we are a member of a bridge device
            bridge = is_member(config, f'{ifname}.{vif_s}.{vif_c}', 'bridge')
            if bridge: dict['vif_s'][vif_s]['vif_c'][vif_c].update(
                {'is_bridge_member' : bridge})

            # Check if any DHCP options changed which require a client restat
            dhcp = is_node_changed(config, base + [ifname, 'vif-s', vif_s, 'vif-c', vif_c, 'dhcp-options'])
            if dhcp: dict['vif_s'][vif_s]['vif_c'][vif_c].update({'dhcp_options_changed' : {}})

    # Check vif, vif-s/vif-c VLAN interfaces for removal
    dict = get_removed_vlans(config, base + [ifname], dict)
    return ifname, dict

def get_vlan_ids(interface):
    """
    Get the VLAN ID of the interface bound to the bridge
    """
    vlan_ids = set()

    bridge_status = cmd('bridge -j vlan show', shell=True)
    vlan_filter_status = json.loads(bridge_status)

    if vlan_filter_status is not None:
        for interface_status in vlan_filter_status:
            ifname = interface_status['ifname']
            if interface == ifname:
                vlans_status = interface_status['vlans']
                for vlan_status in vlans_status:
                    vlan_id = vlan_status['vlan']
                    vlan_ids.add(vlan_id)

    return vlan_ids

def get_accel_dict(config, base, chap_secrets, with_pki=False):
    """
    Common utility function to retrieve and mangle the Accel-PPP configuration
    from different CLI input nodes. All Accel-PPP services have a common base
    where value retrival is identical. This function must be used whenever
    possible when working with Accel-PPP services!

    Return a dictionary with the necessary interface config keys.
    """
    from vyos.cpu import get_core_count
    from vyos.template import is_ipv4

    dict = config.get_config_dict(base, key_mangling=('-', '_'),
                                  get_first_key=True,
                                  no_tag_node_value_mangle=True,
                                  with_recursive_defaults=True,
                                  with_pki=with_pki)

    # set CPUs cores to process requests
    dict.update({'thread_count' : get_core_count()})
    # we need to store the path to the secrets file
    dict.update({'chap_secrets_file' : chap_secrets})

    # We can only have two IPv4 and three IPv6 nameservers - also they are
    # configured in a different way in the configuration, this is why we split
    # the configuration
    if 'name_server' in dict:
        ns_v4 = []
        ns_v6 = []
        for ns in dict['name_server']:
            if is_ipv4(ns): ns_v4.append(ns)
            else: ns_v6.append(ns)

        dict.update({'name_server_ipv4' : ns_v4, 'name_server_ipv6' : ns_v6})
        del dict['name_server']

    # Check option "disable-accounting" per server and replace default value from '1813' to '0'
    for server in (dict_search('authentication.radius.server', dict) or []):
        if 'disable_accounting' in dict['authentication']['radius']['server'][server]:
            dict['authentication']['radius']['server'][server]['acct_port'] = '0'

    return dict
