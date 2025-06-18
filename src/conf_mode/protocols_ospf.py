#!/usr/bin/env python3
#
# Copyright (C) 2021-2025 VyOS maintainers and contributors
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

from vyos.base import Warning
from vyos.config import Config
from vyos.configverify import verify_common_route_maps
from vyos.configverify import verify_route_map
from vyos.configverify import verify_interface_exists
from vyos.configverify import verify_access_list
from vyos.configverify import has_frr_protocol_in_dict
from vyos.frrender import FRRender
from vyos.frrender import get_frrender_dict
from vyos.utils.dict import dict_search
from vyos.utils.network import get_interface_config
from vyos.utils.process import is_systemd_service_running
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    return get_frrender_dict(conf, argv)

def verify(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'ospf'):
        return None

    vrf = None
    if 'vrf_context' in config_dict:
        vrf = config_dict['vrf_context']

    # eqivalent of the C foo ? 'a' : 'b' statement
    ospf = vrf and config_dict['vrf']['name'][vrf]['protocols']['ospf'] or config_dict['ospf']
    ospf['policy'] = config_dict['policy']

    verify_common_route_maps(ospf)

    # As we can have a default-information route-map, we need to validate it!
    route_map_name = dict_search('default_information.originate.route_map', ospf)
    if route_map_name: verify_route_map(route_map_name, ospf)

    # Validate if configured Access-list exists
    if 'area' in ospf:
          networks = []
          for area, area_config in ospf['area'].items():
              # Implemented as warning to not break existing configurations
              if area == '0' and dict_search('area_type.nssa', area_config) != None:
                  Warning('You cannot configure NSSA to backbone!')
              # Implemented as warning to not break existing configurations
              if area == '0' and dict_search('area_type.stub', area_config) != None:
                  Warning('You cannot configure STUB to backbone!')
              # Implemented as warning to not break existing configurations
              if len(area_config['area_type']) > 1:
                  Warning(f'Only one area-type is supported for area "{area}"!')

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
            verify_interface_exists(ospf, interface)
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
            if vrf:
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

def generate(config_dict):
    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().generate(config_dict)
    return None

def apply(config_dict):
    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().apply()
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
