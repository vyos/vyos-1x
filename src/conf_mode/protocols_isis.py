#!/usr/bin/env python3
#
# Copyright (C) 2020-2024 VyOS maintainers and contributors
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
from vyos.configdict import dict_merge
from vyos.configdict import node_changed
from vyos.configverify import verify_common_route_maps
from vyos.configverify import verify_interface_exists
from vyos.ifconfig import Interface
from vyos.utils.dict import dict_search
from vyos.utils.network import get_interface_config
from vyos.template import render_to_string
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

    base_path = ['protocols', 'isis']

    # eqivalent of the C foo ? 'a' : 'b' statement
    base = vrf and ['vrf', 'name', vrf, 'protocols', 'isis'] or base_path
    isis = conf.get_config_dict(base, key_mangling=('-', '_'),
                                get_first_key=True,
                                no_tag_node_value_mangle=True)

    # Assign the name of our VRF context. This MUST be done before the return
    # statement below, else on deletion we will delete the default instance
    # instead of the VRF instance.
    if vrf: isis['vrf'] = vrf

    # FRR has VRF support for different routing daemons. As interfaces belong
    # to VRFs - or the global VRF, we need to check for changed interfaces so
    # that they will be properly rendered for the FRR config. Also this eases
    # removal of interfaces from the running configuration.
    interfaces_removed = node_changed(conf, base + ['interface'])
    if interfaces_removed:
        isis['interface_removed'] = list(interfaces_removed)

    # Bail out early if configuration tree does no longer exist. this must
    # be done after retrieving the list of interfaces to be removed.
    if not conf.exists(base):
        isis.update({'deleted' : ''})
        return isis

    # merge in default values
    isis = conf.merge_defaults(isis, recursive=True)

    # We also need some additional information from the config, prefix-lists
    # and route-maps for instance. They will be used in verify().
    #
    # XXX: one MUST always call this without the key_mangling() option! See
    # vyos.configverify.verify_common_route_maps() for more information.
    tmp = conf.get_config_dict(['policy'])
    # Merge policy dict into "regular" config dict
    isis = dict_merge(tmp, isis)

    return isis

def verify(isis):
    # bail out early - looks like removal from running config
    if not isis or 'deleted' in isis:
        return None

    if 'net' not in isis:
        raise ConfigError('Network entity is mandatory!')

    # last byte in IS-IS area address must be 0
    tmp = isis['net'].split('.')
    if int(tmp[-1]) != 0:
        raise ConfigError('Last byte of IS-IS network entity title must always be 0!')

    verify_common_route_maps(isis)

    # If interface not set
    if 'interface' not in isis:
        raise ConfigError('Interface used for routing updates is mandatory!')

    for interface in isis['interface']:
        verify_interface_exists(isis, interface)
        # Interface MTU must be >= configured lsp-mtu
        mtu = Interface(interface).get_mtu()
        area_mtu = isis['lsp_mtu']
        # Recommended maximum PDU size = interface MTU - 3 bytes
        recom_area_mtu = mtu - 3
        if mtu < int(area_mtu) or int(area_mtu) > recom_area_mtu:
            raise ConfigError(f'Interface {interface} has MTU {mtu}, ' \
                              f'current area MTU is {area_mtu}! \n' \
                              f'Recommended area lsp-mtu {recom_area_mtu} or less ' \
                              '(calculated on MTU size).')

        if 'vrf' in isis:
            # If interface specific options are set, we must ensure that the
            # interface is bound to our requesting VRF. Due to the VyOS
            # priorities the interface is bound to the VRF after creation of
            # the VRF itself, and before any routing protocol is configured.
            vrf = isis['vrf']
            tmp = get_interface_config(interface)
            if 'master' not in tmp or tmp['master'] != vrf:
                raise ConfigError(f'Interface "{interface}" is not a member of VRF "{vrf}"!')

    # If md5 and plaintext-password set at the same time
    for password in ['area_password', 'domain_password']:
        if password in isis:
            if {'md5', 'plaintext_password'} <= set(isis[password]):
                tmp = password.replace('_', '-')
                raise ConfigError(f'Can use either md5 or plaintext-password for {tmp}!')

    # If one param from delay set, but not set others
    if 'spf_delay_ietf' in isis:
        required_timers = ['holddown', 'init_delay', 'long_delay', 'short_delay', 'time_to_learn']
        exist_timers = []
        for elm_timer in required_timers:
            if elm_timer in isis['spf_delay_ietf']:
                exist_timers.append(elm_timer)

        exist_timers = set(required_timers).difference(set(exist_timers))
        if len(exist_timers) > 0:
            raise ConfigError('All types of spf-delay must be configured. Missing: ' + ', '.join(exist_timers).replace('_', '-'))

    # If Redistribute set, but level don't set
    if 'redistribute' in isis:
        proc_level = isis.get('level','').replace('-','_')
        for afi in ['ipv4', 'ipv6']:
            if afi not in isis['redistribute']:
                continue

            for proto, proto_config in isis['redistribute'][afi].items():
                if 'level_1' not in proto_config and 'level_2' not in proto_config:
                    raise ConfigError(f'Redistribute level-1 or level-2 should be specified in ' \
                                      f'"protocols isis redistribute {afi} {proto}"!')

                for redistr_level, redistr_config in proto_config.items():
                    if proc_level and proc_level != 'level_1_2' and proc_level != redistr_level:
                        raise ConfigError(f'"protocols isis redistribute {afi} {proto} {redistr_level}" ' \
                                          f'can not be used with \"protocols isis level {proc_level}\"!')

    # Segment routing checks
    if dict_search('segment_routing.global_block', isis):
        g_high_label_value = dict_search('segment_routing.global_block.high_label_value', isis)
        g_low_label_value = dict_search('segment_routing.global_block.low_label_value', isis)

        # If segment routing global block high or low value is blank, throw error
        if not (g_low_label_value or g_high_label_value):
            raise ConfigError('Segment routing global-block requires both low and high value!')

        # If segment routing global block low value is higher than the high value, throw error
        if int(g_low_label_value) > int(g_high_label_value):
            raise ConfigError('Segment routing global-block low value must be lower than high value')

    if dict_search('segment_routing.local_block', isis):
        if dict_search('segment_routing.global_block', isis) == None:
            raise ConfigError('Segment routing local-block requires global-block to be configured!')

        l_high_label_value = dict_search('segment_routing.local_block.high_label_value', isis)
        l_low_label_value = dict_search('segment_routing.local_block.low_label_value', isis)

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
    if dict_search('segment_routing.prefix', isis):
        for prefix, prefix_config in isis['segment_routing']['prefix'].items():
            if 'absolute' in prefix_config:
                if prefix_config['absolute'].get('value') is None:
                    raise ConfigError(f'Segment routing prefix {prefix} absolute value cannot be blank.')
            elif 'index' in prefix_config:
                if prefix_config['index'].get('value') is None:
                    raise ConfigError(f'Segment routing prefix {prefix} index value cannot be blank.')

    # Check for explicit-null and no-php-flag configured at the same time per prefix
    if dict_search('segment_routing.prefix', isis):
        for prefix, prefix_config in isis['segment_routing']['prefix'].items():
            if 'absolute' in prefix_config:
                if ("explicit_null" in prefix_config['absolute']) and ("no_php_flag" in prefix_config['absolute']):
                    raise ConfigError(f'Segment routing prefix {prefix} cannot have both explicit-null '\
                                      f'and no-php-flag configured at the same time.')
            elif 'index' in prefix_config:
                if ("explicit_null" in prefix_config['index']) and ("no_php_flag" in prefix_config['index']):
                    raise ConfigError(f'Segment routing prefix {prefix} cannot have both explicit-null '\
                                      f'and no-php-flag configured at the same time.')

    # Check for index ranges being larger than the segment routing global block
    if dict_search('segment_routing.global_block', isis):
        g_high_label_value = dict_search('segment_routing.global_block.high_label_value', isis)
        g_low_label_value = dict_search('segment_routing.global_block.low_label_value', isis)
        g_label_difference = int(g_high_label_value) - int(g_low_label_value)
        if dict_search('segment_routing.prefix', isis):
            for prefix, prefix_config in isis['segment_routing']['prefix'].items():
                if 'index' in prefix_config:
                    index_size = isis['segment_routing']['prefix'][prefix]['index']['value']
                    if int(index_size) > int(g_label_difference):
                        raise ConfigError(f'Segment routing prefix {prefix} cannot have an '\
                                          f'index base size larger than the SRGB label base.')

    # Check for LFA tiebreaker index duplication
    if dict_search('fast_reroute.lfa.local.tiebreaker', isis):
        comparison_dictionary = {}
        for item, item_options in isis['fast_reroute']['lfa']['local']['tiebreaker'].items():
            for index, index_options in item_options.items():
                for index_value, index_value_options in index_options.items():
                    if index_value not in comparison_dictionary.keys():
                        comparison_dictionary[index_value] = [item]
                    else:
                        comparison_dictionary[index_value].append(item)
        for index, index_length in comparison_dictionary.items():
            if int(len(index_length)) > 1:
                raise ConfigError(f'LFA index {index} cannot have more than one tiebreaker configured.')

    # Check for LFA priority-limit configured multiple times per level
    if dict_search('fast_reroute.lfa.local.priority_limit', isis):
        comparison_dictionary = {}
        for priority, priority_options in isis['fast_reroute']['lfa']['local']['priority_limit'].items():
            for level, level_options in priority_options.items():
                if level not in comparison_dictionary.keys():
                    comparison_dictionary[level] = [priority]
                else:
                    comparison_dictionary[level].append(priority)
            for level, level_length in comparison_dictionary.items():
                if int(len(level_length)) > 1:
                    raise ConfigError(f'LFA priority-limit on {level.replace("_", "-")} cannot have more than one priority configured.')

    # Check for LFA remote prefix list configured with more than one list
    if dict_search('fast_reroute.lfa.remote.prefix_list', isis):
        if int(len(isis['fast_reroute']['lfa']['remote']['prefix_list'].items())) > 1:
            raise ConfigError(f'LFA remote prefix-list has more than one configured. Cannot have more than one configured.')

    return None

def generate(isis):
    if not isis or 'deleted' in isis:
        return None

    isis['frr_isisd_config'] = render_to_string('frr/isisd.frr.j2', isis)
    return None

def apply(isis):
    isis_daemon = 'isisd'

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()

    # Generate empty helper string which can be ammended to FRR commands, it
    # will be either empty (default VRF) or contain the "vrf <name" statement
    vrf = ''
    if 'vrf' in isis:
        vrf = ' vrf ' + isis['vrf']

    frr_cfg.load_configuration(isis_daemon)
    frr_cfg.modify_section(f'^router isis VyOS{vrf}', stop_pattern='^exit', remove_stop_mark=True)

    for key in ['interface', 'interface_removed']:
        if key not in isis:
            continue
        for interface in isis[key]:
            frr_cfg.modify_section(f'^interface {interface}', stop_pattern='^exit', remove_stop_mark=True)

    if 'frr_isisd_config' in isis:
        frr_cfg.add_before(frr.default_add_before, isis['frr_isisd_config'])

    frr_cfg.commit_configuration(isis_daemon)

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
