#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from sys import exit
from sys import argv

from vyos.config import Config
from vyos.config import config_dict_merge
from vyos.configdict import dict_merge
from vyos.configdict import node_changed
from vyos.configverify import verify_common_route_maps
from vyos.configverify import verify_route_map
from vyos.configverify import verify_interface_exists
from vyos.configverify import verify_access_list
from vyos.template import render_to_string
from vyos.utils.dict import dict_search
from vyos.utils.network import get_interface_config
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    vrf = None
    if len(argv) > 1:
        vrf = argv[1]

    base_path = ['protocols', 'ospf']

    # eqivalent of the C foo ? 'a' : 'b' statement
    base = vrf and ['vrf', 'name', vrf, 'protocols', 'ospf'] or base_path
    ospf = conf.get_config_dict(base, key_mangling=('-', '_'),
                                get_first_key=True)

    # Assign the name of our VRF context. This MUST be done before the return
    # statement below, else on deletion we will delete the default instance
    # instead of the VRF instance.
    if vrf: ospf['vrf'] = vrf

    # FRR has VRF support for different routing daemons. As interfaces belong
    # to VRFs - or the global VRF, we need to check for changed interfaces so
    # that they will be properly rendered for the FRR config. Also this eases
    # removal of interfaces from the running configuration.
    interfaces_removed = node_changed(conf, base + ['interface'])
    if interfaces_removed:
        ospf['interface_removed'] = list(interfaces_removed)

    # Bail out early if configuration tree does no longer exist. this must
    # be done after retrieving the list of interfaces to be removed.
    if not conf.exists(base):
        ospf.update({'deleted' : ''})
        return ospf

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = conf.get_config_defaults(**ospf.kwargs, recursive=True)

    # We have to cleanup the default dict, as default values could enable features
    # which are not explicitly enabled on the CLI. Example: default-information
    # originate comes with a default metric-type of 2, which will enable the
    # entire default-information originate tree, even when not set via CLI so we
    # need to check this first and probably drop that key.
    if dict_search('default_information.originate', ospf) is None:
        del default_values['default_information']
    if 'mpls_te' not in ospf:
        del default_values['mpls_te']
    if 'graceful_restart' not in ospf:
        del default_values['graceful_restart']
    for area_num in default_values.get('area', []):
        if dict_search(f'area.{area_num}.area_type.nssa', ospf) is None:
            del default_values['area'][area_num]['area_type']['nssa']

    for protocol in ['babel', 'bgp', 'connected', 'isis', 'kernel', 'rip', 'static']:
        if dict_search(f'redistribute.{protocol}', ospf) is None:
            del default_values['redistribute'][protocol]
    if not bool(default_values['redistribute']):
        del default_values['redistribute']

    for interface in ospf.get('interface', []):
        # We need to reload the defaults on every pass b/c of
        # hello-multiplier dependency on dead-interval
        # If hello-multiplier is set, we need to remove the default from
        # dead-interval.
        if 'hello_multiplier' in ospf['interface'][interface]:
            del default_values['interface'][interface]['dead_interval']

    ospf = config_dict_merge(default_values, ospf)

    # We also need some additional information from the config, prefix-lists
    # and route-maps for instance. They will be used in verify().
    #
    # XXX: one MUST always call this without the key_mangling() option! See
    # vyos.configverify.verify_common_route_maps() for more information.
    tmp = conf.get_config_dict(['policy'])
    # Merge policy dict into "regular" config dict
    ospf = dict_merge(tmp, ospf)

    return ospf

def verify(ospf):
    if not ospf:
        return None

    verify_common_route_maps(ospf)

    # As we can have a default-information route-map, we need to validate it!
    route_map_name = dict_search('default_information.originate.route_map', ospf)
    if route_map_name: verify_route_map(route_map_name, ospf)

    # Validate if configured Access-list exists
    if 'area' in ospf:
          networks = []
          for area, area_config in ospf['area'].items():
              if 'import_list' in area_config:
                  acl_import = area_config['import_list']
                  if acl_import: verify_access_list(acl_import, ospf)
              if 'export_list' in area_config:
                  acl_export = area_config['export_list']
                  if acl_export: verify_access_list(acl_export, ospf)

              if 'network' in area_config:
                  for network in area_config['network']:
                      if network in networks:
                          raise ConfigError(f'Network "{network}" already defined in different area!')
                      networks.append(network)

    if 'interface' in ospf:
        for interface, interface_config in ospf['interface'].items():
            verify_interface_exists(interface)
            # One can not use dead-interval and hello-multiplier at the same
            # time. FRR will only activate the last option set via CLI.
            if {'hello_multiplier', 'dead_interval'} <= set(interface_config):
                raise ConfigError(f'Can not use hello-multiplier and dead-interval ' \
                                  f'concurrently for {interface}!')

            # One can not use the "network <prefix> area <id>" command and an
            # per interface area assignment at the same time. FRR will error
            # out using: "Please remove all network commands first."
            if 'area' in ospf and 'area' in interface_config:
                for area, area_config in ospf['area'].items():
                    if 'network' in area_config:
                        raise ConfigError('Can not use OSPF interface area and area ' \
                                          'network configuration at the same time!')

            # If interface specific options are set, we must ensure that the
            # interface is bound to our requesting VRF. Due to the VyOS
            # priorities the interface is bound to the VRF after creation of
            # the VRF itself, and before any routing protocol is configured.
            if 'vrf' in ospf:
                vrf = ospf['vrf']
                tmp = get_interface_config(interface)
                if 'master' not in tmp or tmp['master'] != vrf:
                    raise ConfigError(f'Interface "{interface}" is not a member of VRF "{vrf}"!')

    # Segment routing checks
    if dict_search('segment_routing.global_block', ospf):
        g_high_label_value = dict_search('segment_routing.global_block.high_label_value', ospf)
        g_low_label_value = dict_search('segment_routing.global_block.low_label_value', ospf)

        # If segment routing global block high or low value is blank, throw error
        if not (g_low_label_value or g_high_label_value):
            raise ConfigError('Segment routing global-block requires both low and high value!')

        # If segment routing global block low value is higher than the high value, throw error
        if int(g_low_label_value) > int(g_high_label_value):
            raise ConfigError('Segment routing global-block low value must be lower than high value')

    if dict_search('segment_routing.local_block', ospf):
        if dict_search('segment_routing.global_block', ospf) == None:
            raise ConfigError('Segment routing local-block requires global-block to be configured!')

        l_high_label_value = dict_search('segment_routing.local_block.high_label_value', ospf)
        l_low_label_value = dict_search('segment_routing.local_block.low_label_value', ospf)

        # If segment routing local-block high or low value is blank, throw error
        if not (l_low_label_value or l_high_label_value):
            raise ConfigError('Segment routing local-block requires both high and low value!')

        # If segment routing local-block low value is higher than the high value, throw error
        if int(l_low_label_value) > int(l_high_label_value):
            raise ConfigError('Segment routing local-block low value must be lower than high value')

        # local-block most live outside global block
        global_range = range(int(g_low_label_value), int(g_high_label_value) +1)
        local_range  = range(int(l_low_label_value), int(l_high_label_value) +1)

        # Check for overlapping ranges
        if list(set(global_range) & set(local_range)):
            raise ConfigError(f'Segment-Routing Global Block ({g_low_label_value}/{g_high_label_value}) '\
                              f'conflicts with Local Block ({l_low_label_value}/{l_high_label_value})!')

    # Check for a blank or invalid value per prefix
    if dict_search('segment_routing.prefix', ospf):
        for prefix, prefix_config in ospf['segment_routing']['prefix'].items():
            if 'index' in prefix_config:
                if prefix_config['index'].get('value') is None:
                    raise ConfigError(f'Segment routing prefix {prefix} index value cannot be blank.')

    # Check for explicit-null and no-php-flag configured at the same time per prefix
    if dict_search('segment_routing.prefix', ospf):
        for prefix, prefix_config in ospf['segment_routing']['prefix'].items():
            if 'index' in prefix_config:
                if ("explicit_null" in prefix_config['index']) and ("no_php_flag" in prefix_config['index']):
                    raise ConfigError(f'Segment routing prefix {prefix} cannot have both explicit-null '\
                                      f'and no-php-flag configured at the same time.')

    # Check for index ranges being larger than the segment routing global block
    if dict_search('segment_routing.global_block', ospf):
        g_high_label_value = dict_search('segment_routing.global_block.high_label_value', ospf)
        g_low_label_value = dict_search('segment_routing.global_block.low_label_value', ospf)
        g_label_difference = int(g_high_label_value) - int(g_low_label_value)
        if dict_search('segment_routing.prefix', ospf):
            for prefix, prefix_config in ospf['segment_routing']['prefix'].items():
                if 'index' in prefix_config:
                    index_size = ospf['segment_routing']['prefix'][prefix]['index']['value']
                    if int(index_size) > int(g_label_difference):
                        raise ConfigError(f'Segment routing prefix {prefix} cannot have an '\
                                          f'index base size larger than the SRGB label base.')

    # Check route summarisation
    if 'summary_address' in ospf:
        for prefix, prefix_options in ospf['summary_address'].items():
            if {'tag', 'no_advertise'} <= set(prefix_options):
                raise ConfigError(f'Can not set both "tag" and "no-advertise" for Type-5 '\
                                  f'and Type-7 route summarisation of "{prefix}"!')

    return None

def generate(ospf):
    if not ospf or 'deleted' in ospf:
        return None

    ospf['frr_ospfd_config'] = render_to_string('frr/ospfd.frr.j2', ospf)
    return None

def apply(ospf):
    ospf_daemon = 'ospfd'

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()

    # Generate empty helper string which can be ammended to FRR commands, it
    # will be either empty (default VRF) or contain the "vrf <name" statement
    vrf = ''
    if 'vrf' in ospf:
        vrf = ' vrf ' + ospf['vrf']

    frr_cfg.load_configuration(ospf_daemon)
    frr_cfg.modify_section(f'^router ospf{vrf}', stop_pattern='^exit', remove_stop_mark=True)

    for key in ['interface', 'interface_removed']:
        if key not in ospf:
            continue
        for interface in ospf[key]:
            frr_cfg.modify_section(f'^interface {interface}', stop_pattern='^exit', remove_stop_mark=True)

    if 'frr_ospfd_config' in ospf:
        frr_cfg.add_before(frr.default_add_before, ospf['frr_ospfd_config'])

    frr_cfg.commit_configuration(ospf_daemon)

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
