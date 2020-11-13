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

from vyos.util import dict_search
from vyos.xml import defaults
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
    if dict_search('dhcpv6_options.pd.length', config_dict):
        del config_dict['dhcpv6_options']['pd']['length']

    for pd in (dict_search('dhcpv6_options.pd', config_dict) or []):
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

    for iftype in intftype:
        base = ['interfaces', iftype]
        for intf in conf.list_nodes(base):
            member = base + [intf, 'member', 'interface', interface]
            if conf.exists(member):
                tmp = conf.get_config_dict(member, key_mangling=('-', '_'), get_first_key=True)
                ret_val = {intf : tmp}

    old_level = conf.set_level(old_level)
    return ret_val

def has_vlan_subinterface_configured(conf, intf):
    """
    Checks if interface has an VLAN subinterface configured.
    Checks the following config nodes:
    'vif', 'vif-s'

    Returns True if interface has VLAN subinterface configured, False if it doesn't.
    """
    from vyos.ifconfig import Section
    ret = False

    old_level = conf.get_level()
    conf.set_level([])

    intfpath = 'interfaces ' + Section.get_config_path(intf)
    if ( conf.exists(f'{intfpath} vif') or
            conf.exists(f'{intfpath} vif-s')):
        ret = True

    conf.set_level(old_level)
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
    Common utility function to retrieve and mangle the interfaces configuration
    from the CLI input nodes. All interfaces have a common base where value
    retrival is identical. This function must be used whenever possible when
    working on the interfaces node!

    Return a dictionary with the necessary interface config keys.
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

    # Check if interface has been removed. We must use exists() as get_config_dict()
    # will always return {} - even when an empty interface node like
    # +macsec macsec1 {
    # +}
    # exists.
    if not config.exists([]):
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
        tmp = dict_search('ipv6.address', dict)
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

        # Check if we are a member of a bridge device
        bridge = is_member(config, f'{ifname}.{vif}', 'bridge')
        if bridge: dict['vif'][vif].update({'is_bridge_member' : bridge})

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

        # Check if we are a member of a bridge device
        bridge = is_member(config, f'{ifname}.{vif_s}', 'bridge')
        if bridge: dict['vif_s'][vif_s].update({'is_bridge_member' : bridge})

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

            # Check if we are a member of a bridge device
            bridge = is_member(config, f'{ifname}.{vif_s}.{vif_c}', 'bridge')
            if bridge: dict['vif_s'][vif_s]['vif_c'][vif_c].update(
                {'is_bridge_member' : bridge})

    # Check vif, vif-s/vif-c VLAN interfaces for removal
    dict = get_removed_vlans(config, dict)
    return dict


def get_accel_dict(config, base, chap_secrets):
    """
    Common utility function to retrieve and mangle the Accel-PPP configuration
    from different CLI input nodes. All Accel-PPP services have a common base
    where value retrival is identical. This function must be used whenever
    possible when working with Accel-PPP services!

    Return a dictionary with the necessary interface config keys.
    """
    from vyos.util import get_half_cpus
    from vyos.template import is_ipv4

    dict = config.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)

    # defaults include RADIUS server specifics per TAG node which need to be
    # added to individual RADIUS servers instead - so we can simply delete them
    if dict_search('authentication.radius.server', default_values):
        del default_values['authentication']['radius']['server']

    # defaults include static-ip address per TAG node which need to be added to
    # individual local users instead - so we can simply delete them
    if dict_search('authentication.local_users.username', default_values):
        del default_values['authentication']['local_users']['username']

    dict = dict_merge(default_values, dict)

    # set CPUs cores to process requests
    dict.update({'thread_count' : get_half_cpus()})
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

    # Add individual RADIUS server default values
    if dict_search('authentication.radius.server', dict):
        default_values = defaults(base + ['authentication', 'radius', 'server'])

        for server in dict_search('authentication.radius.server', dict):
            dict['authentication']['radius']['server'][server] = dict_merge(
                default_values, dict['authentication']['radius']['server'][server])

            # Check option "disable-accounting" per server and replace default value from '1813' to '0'
            # set vpn sstp authentication radius server x.x.x.x disable-accounting
            if 'disable_accounting' in dict['authentication']['radius']['server'][server]:
                dict['authentication']['radius']['server'][server]['acct_port'] = '0'

    # Add individual local-user default values
    if dict_search('authentication.local_users.username', dict):
        default_values = defaults(base + ['authentication', 'local-users', 'username'])

        for username in dict_search('authentication.local_users.username', dict):
            dict['authentication']['local_users']['username'][username] = dict_merge(
                default_values, dict['authentication']['local_users']['username'][username])

    return dict
