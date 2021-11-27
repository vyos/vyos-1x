#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

import os

from sys import exit
from sys import argv

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configdict import node_changed
from vyos.configverify import verify_common_route_maps
from vyos.configverify import verify_route_map
from vyos.configverify import verify_interface_exists
from vyos.template import render_to_string
from vyos.util import dict_search
from vyos.util import get_interface_config
from vyos.xml import defaults
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

    # Bail out early if configuration tree does not exist
    if not conf.exists(base):
        ospf.update({'deleted' : ''})
        return ospf

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    # XXX: Note that we can not call defaults(base), as defaults does not work
    # on an instance of a tag node. As we use the exact same CLI definition for
    # both the non-vrf and vrf version this is absolutely safe!
    default_values = defaults(base_path)

    # We have to cleanup the default dict, as default values could enable features
    # which are not explicitly enabled on the CLI. Example: default-information
    # originate comes with a default metric-type of 2, which will enable the
    # entire default-information originate tree, even when not set via CLI so we
    # need to check this first and probably drop that key.
    if dict_search('default_information.originate', ospf) is None:
        del default_values['default_information']
    if dict_search('area.area_type.nssa', ospf) is None:
        del default_values['area']['area_type']['nssa']
    if 'mpls_te' not in ospf:
        del default_values['mpls_te']

    for protocol in ['bgp', 'connected', 'isis', 'kernel', 'rip', 'static', 'table']:
        # table is a tagNode thus we need to clean out all occurances for the
        # default values and load them in later individually
        if protocol == 'table':
            del default_values['redistribute']['table']
            continue
        if dict_search(f'redistribute.{protocol}', ospf) is None:
            del default_values['redistribute'][protocol]

    # XXX: T2665: we currently have no nice way for defaults under tag nodes,
    # clean them out and add them manually :(
    del default_values['neighbor']
    del default_values['area']['virtual_link']
    del default_values['interface']

    # merge in remaining default values
    ospf = dict_merge(default_values, ospf)

    if 'neighbor' in ospf:
        default_values = defaults(base + ['neighbor'])
        for neighbor in ospf['neighbor']:
            ospf['neighbor'][neighbor] = dict_merge(default_values, ospf['neighbor'][neighbor])

    if 'area' in ospf:
        default_values = defaults(base + ['area', 'virtual-link'])
        for area, area_config in ospf['area'].items():
            if 'virtual_link' in area_config:
                for virtual_link in area_config['virtual_link']:
                    ospf['area'][area]['virtual_link'][virtual_link] = dict_merge(
                        default_values, ospf['area'][area]['virtual_link'][virtual_link])

    if 'interface' in ospf:
        for interface in ospf['interface']:
            # We need to reload the defaults on every pass b/c of
            # hello-multiplier dependency on dead-interval
            default_values = defaults(base + ['interface'])
            # If hello-multiplier is set, we need to remove the default from
            # dead-interval.
            if 'hello_multiplier' in ospf['interface'][interface]:
                del default_values['dead_interval']

            ospf['interface'][interface] = dict_merge(default_values,
                ospf['interface'][interface])

    if 'redistribute' in ospf and 'table' in ospf['redistribute']:
        default_values = defaults(base + ['redistribute', 'table'])
        for table in ospf['redistribute']['table']:
            ospf['redistribute']['table'][table] = dict_merge(default_values,
                ospf['redistribute']['table'][table])

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

            if 'vrf' in ospf:
            # If interface specific options are set, we must ensure that the
            # interface is bound to our requesting VRF. Due to the VyOS
            # priorities the interface is bound to the VRF after creation of
            # the VRF itself, and before any routing protocol is configured.
                vrf = ospf['vrf']
                tmp = get_interface_config(interface)
                if 'master' not in tmp or tmp['master'] != vrf:
                    raise ConfigError(f'Interface {interface} is not a member of VRF {vrf}!')

    return None

def generate(ospf):
    if not ospf or 'deleted' in ospf:
        return None

    ospf['protocol'] = 'ospf' # required for frr/vrf.route-map.frr.tmpl
    ospf['frr_zebra_config'] = render_to_string('frr/vrf.route-map.frr.tmpl', ospf)
    ospf['frr_ospfd_config'] = render_to_string('frr/ospfd.frr.tmpl', ospf)
    return None

def apply(ospf):
    ospf_daemon = 'ospfd'
    zebra_daemon = 'zebra'

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()

    # The route-map used for the FIB (zebra) is part of the zebra daemon
    frr_cfg.load_configuration(zebra_daemon)
    frr_cfg.modify_section('(\s+)?ip protocol ospf route-map [-a-zA-Z0-9.]+', stop_pattern='(\s|!)')
    if 'frr_zebra_config' in ospf:
        frr_cfg.add_before(frr.default_add_before, ospf['frr_zebra_config'])
    frr_cfg.commit_configuration(zebra_daemon)

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
            frr_cfg.modify_section(f'^interface {interface}{vrf}', stop_pattern='^exit', remove_stop_mark=True)

    if 'frr_ospfd_config' in ospf:
        frr_cfg.add_before(frr.default_add_before, ospf['frr_ospfd_config'])
    frr_cfg.commit_configuration(ospf_daemon)

    # Save configuration to /run/frr/config/frr.conf
    frr.save_configuration()

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
