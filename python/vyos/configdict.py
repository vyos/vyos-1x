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
import jmespath

from enum import Enum
from copy import deepcopy

from vyos import ConfigError
from vyos.validate import is_member

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
        if key not in tmp.keys():
            tmp[key] = value
        elif isinstance(source[key], dict):
            tmp[key] = dict_merge(source[key], tmp[key])

    return tmp

def list_diff(first, second):
    """ Diff two dictionaries and return only unique items """
    second = set(second)
    return [item for item in first if item not in second]

def T2665_default_dict_cleanup(dict):
    """ Cleanup default keys for tag nodes https://phabricator.vyos.net/T2665. """
    # Cleanup
    for vif in ['vif', 'vif_s']:
        if vif in dict.keys():
            for key in ['ip', 'mtu']:
                if key in dict[vif].keys():
                    del dict[vif][key]

            # cleanup VIF-S defaults
            if 'vif_c' in dict[vif].keys():
                for key in ['ip', 'mtu']:
                    if key in dict[vif]['vif_c'].keys():
                        del dict[vif]['vif_c'][key]
                # If there is no vif-c defined and we just cleaned the default
                # keys - we can clean the entire vif-c dict as it's useless
                if not dict[vif]['vif_c']:
                    del dict[vif]['vif_c']

            # If there is no real vif/vif-s defined and we just cleaned the default
            # keys - we can clean the entire vif dict as it's useless
            if not dict[vif]:
                del dict[vif]

    return dict

def leaf_node_changed(conf, path):
    """
    Check if a leaf node was altered. If it has been altered - values has been
    changed, or it was added/removed, we will return the old value. If nothing
    has been changed, None is returned
    """
    from vyos.configdiff import get_config_diff
    D = get_config_diff(conf, key_mangling=('-', '_'))
    D.set_level(conf.get_level())
    (new, old) = D.get_value_diff(path)
    if new != old:
        if isinstance(old, str):
            return old
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

def get_interface_dict(config, base, ifname=''):
    """
    Common utility function to retrieve and mandgle the interfaces available
    in CLI configuration. All interfaces have a common base ground where the
    value retrival is identical - so it can and should be reused

    Will return a dictionary with the necessary interface configuration
    """
    from vyos.xml import defaults

    if not ifname:
        # determine tagNode instance
        if 'VYOS_TAGNODE_VALUE' not in os.environ:
            raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')
        ifname = os.environ['VYOS_TAGNODE_VALUE']

    # retrieve interface default values
    default_values = defaults(base)

    # setup config level which is extracted in get_removed_vlans()
    config.set_level(base + [ifname])
    dict = config.get_config_dict([], key_mangling=('-', '_'), get_first_key=True)

    # Check if interface has been removed
    if dict == {}:
        dict.update({'deleted' : ''})

    # Add interface instance name into dictionary
    dict.update({'ifname': ifname})

    # We have gathered the dict representation of the CLI, but there are
    # default options which we need to update into the dictionary
    # retrived.
    dict = dict_merge(default_values, dict)

    # Check if we are a member of a bridge device
    bridge = is_member(config, ifname, 'bridge')
    if bridge:
        dict.update({'is_bridge_member' : bridge})

    # Check if we are a member of a bond device
    bond = is_member(config, ifname, 'bonding')
    if bond:
        dict.update({'is_bond_member' : bond})

    mac = leaf_node_changed(config, ['mac'])
    if mac:
        dict.update({'mac_old' : mac})

    eui64 = leaf_node_changed(config, ['ipv6', 'address', 'eui64'])
    if eui64:
        # XXX: T2636 workaround: convert string to a list with one element
        if isinstance(eui64, str):
            eui64 = [eui64]
        tmp = jmespath.search('ipv6.address', dict)
        if not tmp:
            dict.update({'ipv6': {'address': {'eui64_old': eui64}}})
        else:
            dict['ipv6']['address'].update({'eui64_old': eui64})

    # remove wrongly inserted values
    dict = T2665_default_dict_cleanup(dict)

    # The values are identical for vif, vif-s and vif-c as the all include the same
    # XML definitions which hold the defaults
    default_vif_values = defaults(base + ['vif'])
    for vif, vif_config in dict.get('vif', {}).items():
        vif_config = dict_merge(default_vif_values, vif_config)
    for vif_s, vif_s_config in dict.get('vif_s', {}).items():
        vif_s_config = dict_merge(default_vif_values, vif_s_config)
        for vif_c, vif_c_config in vif_s_config.get('vif_c', {}).items():
            vif_c_config = dict_merge(default_vif_values, vif_c_config)

    # Check vif, vif-s/vif-c VLAN interfaces for removal
    dict = get_removed_vlans(config, dict)

    return dict

