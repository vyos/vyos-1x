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
import os

from copy import deepcopy

from vyos.util import vyos_dict_search
from vyos.xml import defaults
from vyos.xml import is_tag
from vyos.xml import is_leaf
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

def leaf_node_changed(conf, path):
    """
    Check if a leaf node was altered. If it has been altered - values has been
    changed, or it was added/removed, we will return a list containing the old
    value(s). If nothing has been changed, None is returned
    """
    from vyos.configdiff import get_config_diff
    D = get_config_diff(conf, key_mangling=('-', '_'))
    D.set_level(conf.get_level())
    (new, old) = D.get_value_diff(path)
    if new != old:
        if isinstance(old, str):
            return [old]
        elif isinstance(old, list):
            if isinstance(new, str):
                new = [new]
            elif isinstance(new, type(None)):
                new = []
            return list_diff(old, new)

    return None

def node_changed(conf, path):
    """
    Check if a leaf node was altered. If it has been altered - values has been
    changed, or it was added/removed, we will return the old value. If nothing
    has been changed, None is returned
    """
    from vyos.configdiff import get_config_diff, Diff
    D = get_config_diff(conf, key_mangling=('-', '_'))
    D.set_level(conf.get_level())
    # get_child_nodes() will return dict_keys(), mangle this into a list with PEP448
    keys = D.get_child_nodes_diff(path, expand_nodes=Diff.DELETE)['delete'].keys()
    return list(keys)

def get_removed_vlans(conf, dict):
    """
    Common function to parse a dictionary retrieved via get_config_dict() and
    determine any added/removed VLAN interfaces - be it 802.1q or Q-in-Q.
    """
    from vyos.configdiff import get_config_diff, Diff

    # Check vif, vif-s/vif-c VLAN interfaces for removal
    D = get_config_diff(conf, key_mangling=('-', '_'))
    D.set_level(conf.get_level())
    # get_child_nodes() will return dict_keys(), mangle this into a list with PEP448
    keys = D.get_child_nodes_diff(['vif'], expand_nodes=Diff.DELETE)['delete'].keys()
    if keys:
        dict.update({'vif_remove': [*keys]})

    # get_child_nodes() will return dict_keys(), mangle this into a list with PEP448
    keys = D.get_child_nodes_diff(['vif-s'], expand_nodes=Diff.DELETE)['delete'].keys()
    if keys:
        dict.update({'vif_s_remove': [*keys]})

    for vif in dict.get('vif_s', {}).keys():
        keys = D.get_child_nodes_diff(['vif-s', vif, 'vif-c'], expand_nodes=Diff.DELETE)['delete'].keys()
        if keys:
            dict.update({'vif_s': { vif : {'vif_c_remove': [*keys]}}})

    return dict

def T2665_set_dhcpv6pd_defaults(config_dict):
    """ Properly configure DHCPv6 default options in the dictionary. If there is
    no DHCPv6 configured at all, it is safe to remove the entire configuration.
    """
    # As this is the same for every interface type it is safe to assume this
    # for ethernet
    pd_defaults = defaults(['interfaces', 'ethernet', 'dhcpv6-options', 'pd'])

    # Implant default dictionary for DHCPv6-PD instances
    if vyos_dict_search('dhcpv6_options.pd.length', config_dict):
        del config_dict['dhcpv6_options']['pd']['length']

    for pd in (vyos_dict_search('dhcpv6_options.pd', config_dict) or []):
        config_dict['dhcpv6_options']['pd'][pd] = dict_merge(pd_defaults,
            config_dict['dhcpv6_options']['pd'][pd])

    return config_dict

def is_member(conf, interface, intftype=None):
    """
    Checks if passed interface is member of other interface of specified type.
    intftype is optional, if not passed it will search all known types
    (currently bridge and bonding)

    Returns:
    None -> Interface is not a member
    interface name -> Interface is a member of this interface
    False -> interface type cannot have members
    """
    ret_val = None
    intftypes = ['bonding', 'bridge']
    if intftype not in intftypes + [None]:
        raise ValueError((
            f'unknown interface type "{intftype}" or it cannot '
            f'have member interfaces'))

    intftype = intftypes if intftype == None else [intftype]

    # set config level to root
    old_level = conf.get_level()
    conf.set_level([])

    for it in intftype:
        base = ['interfaces', it]
        for intf in conf.list_nodes(base):
            memberintf = base + [intf, 'member', 'interface']
            if is_tag(memberintf):
                if interface in conf.list_nodes(memberintf):
                    ret_val = intf
                    break
            elif is_leaf(memberintf):
                if ( conf.exists(memberintf) and
                        interface in conf.return_values(memberintf) ):
                    ret_val = intf
                    break

    old_level = conf.set_level(old_level)
    return ret_val

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
    if intftype not in intftypes + [None]:
        raise ValueError(f'unknown interface type "{intftype}" or it can not '
            'have a source-interface')

    intftype = intftypes if intftype == None else [intftype]

    # set config level to root
    old_level = conf.get_level()
    conf.set_level([])

    for it in intftype:
        base = ['interfaces', it]
        for intf in conf.list_nodes(base):
            lower_intf = base + [intf, 'source-interface']
            if conf.exists(lower_intf) and interface in conf.return_values(lower_intf):
                ret_val = intf
                break

    old_level = conf.set_level(old_level)
    return ret_val

def get_interface_dict(config, base, ifname=''):
    """
    Common utility function to retrieve and mandgle the interfaces available
    in CLI configuration. All interfaces have a common base ground where the
    value retrival is identical - so it can and should be reused

    Will return a dictionary with the necessary interface configuration
    """
    if not ifname:
        # determine tagNode instance
        if 'VYOS_TAGNODE_VALUE' not in os.environ:
            raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')
        ifname = os.environ['VYOS_TAGNODE_VALUE']

    # retrieve interface default values
    default_values = defaults(base)

    # We take care about VLAN (vif, vif-s, vif-c) default values later on when
    # parsing vlans in default dict and merge the "proper" values in correctly,
    # see T2665.
    for vif in ['vif', 'vif_s']:
        if vif in default_values: del default_values[vif]

    # setup config level which is extracted in get_removed_vlans()
    config.set_level(base + [ifname])
    dict = config.get_config_dict([], key_mangling=('-', '_'), get_first_key=True)

    # Check if interface has been removed
    if dict == {}:
        dict.update({'deleted' : ''})

    # Add interface instance name into dictionary
    dict.update({'ifname': ifname})

    # XXX: T2665: When there is no DHCPv6-PD configuration given, we can safely
    # remove the default values from the dict.
    if 'dhcpv6_options' not in dict:
        if 'dhcpv6_options' in default_values:
            del default_values['dhcpv6_options']

    # We have gathered the dict representation of the CLI, but there are
    # default options which we need to update into the dictionary
    # retrived.
    dict = dict_merge(default_values, dict)

    # XXX: T2665: blend in proper DHCPv6-PD default values
    dict = T2665_set_dhcpv6pd_defaults(dict)

    # Check if we are a member of a bridge device
    bridge = is_member(config, ifname, 'bridge')
    if bridge: dict.update({'is_bridge_member' : bridge})

    # Check if we are a member of a bond device
    bond = is_member(config, ifname, 'bonding')
    if bond: dict.update({'is_bond_member' : bond})

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

    mac = leaf_node_changed(config, ['mac'])
    if mac: dict.update({'mac_old' : mac})

    eui64 = leaf_node_changed(config, ['ipv6', 'address', 'eui64'])
    if eui64:
        tmp = vyos_dict_search('ipv6.address', dict)
        if not tmp:
            dict.update({'ipv6': {'address': {'eui64_old': eui64}}})
        else:
            dict['ipv6']['address'].update({'eui64_old': eui64})

    # Implant default dictionary in vif/vif-s VLAN interfaces. Values are
    # identical for all types of VLAN interfaces as they all include the same
    # XML definitions which hold the defaults.
    for vif, vif_config in dict.get('vif', {}).items():
        default_vif_values = defaults(base + ['vif'])
        # XXX: T2665: When there is no DHCPv6-PD configuration given, we can safely
        # remove the default values from the dict.
        if not 'dhcpv6_options' in vif_config:
            del default_vif_values['dhcpv6_options']

        dict['vif'][vif] = dict_merge(default_vif_values, vif_config)
        # XXX: T2665: blend in proper DHCPv6-PD default values
        dict['vif'][vif] = T2665_set_dhcpv6pd_defaults(dict['vif'][vif])

    for vif_s, vif_s_config in dict.get('vif_s', {}).items():
        default_vif_s_values = defaults(base + ['vif-s'])
        # XXX: T2665: we only wan't the vif-s defaults - do not care about vif-c
        if 'vif_c' in default_vif_s_values: del default_vif_s_values['vif_c']

        # XXX: T2665: When there is no DHCPv6-PD configuration given, we can safely
        # remove the default values from the dict.
        if not 'dhcpv6_options' in vif_s_config:
            del default_vif_s_values['dhcpv6_options']

        dict['vif_s'][vif_s] = dict_merge(default_vif_s_values, vif_s_config)
        # XXX: T2665: blend in proper DHCPv6-PD default values
        dict['vif_s'][vif_s] = T2665_set_dhcpv6pd_defaults(
            dict['vif_s'][vif_s])

        for vif_c, vif_c_config in vif_s_config.get('vif_c', {}).items():
            default_vif_c_values = defaults(base + ['vif-s', 'vif-c'])

            # XXX: T2665: When there is no DHCPv6-PD configuration given, we can safely
            # remove the default values from the dict.
            if not 'dhcpv6_options' in vif_c_config:
                del default_vif_c_values['dhcpv6_options']

            dict['vif_s'][vif_s]['vif_c'][vif_c] = dict_merge(
                    default_vif_c_values, vif_c_config)
            # XXX: T2665: blend in proper DHCPv6-PD default values
            dict['vif_s'][vif_s]['vif_c'][vif_c] = T2665_set_dhcpv6pd_defaults(
                dict['vif_s'][vif_s]['vif_c'][vif_c])

    # Check vif, vif-s/vif-c VLAN interfaces for removal
    dict = get_removed_vlans(config, dict)
    return dict
