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
from vyos.configdict import dict_merge
from vyos.configdict import get_dhcp_interfaces
from vyos.configdict import get_pppoe_interfaces
from vyos.configverify import verify_common_route_maps
from vyos.configverify import verify_vrf
from vyos.template import render
from vyos.template import render_to_string
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

config_file = '/etc/iproute2/rt_tables.d/vyos-static.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    vrf = None
    if len(argv) > 1:
        vrf = argv[1]

    base_path = ['protocols', 'static']
    # eqivalent of the C foo ? 'a' : 'b' statement
    base = vrf and ['vrf', 'name', vrf, 'protocols', 'static'] or base_path
    static = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True, no_tag_node_value_mangle=True)

    # Assign the name of our VRF context
    if vrf: static['vrf'] = vrf

    # We also need some additional information from the config, prefix-lists
    # and route-maps for instance. They will be used in verify().
    #
    # XXX: one MUST always call this without the key_mangling() option! See
    # vyos.configverify.verify_common_route_maps() for more information.
    tmp = conf.get_config_dict(['policy'])
    # Merge policy dict into "regular" config dict
    static = dict_merge(tmp, static)

    # T3680 - get a list of all interfaces currently configured to use DHCP
    tmp = get_dhcp_interfaces(conf, vrf)
    if tmp: static.update({'dhcp' : tmp})
    tmp = get_pppoe_interfaces(conf, vrf)
    if tmp: static.update({'pppoe' : tmp})

    return static

def verify(static):
    verify_common_route_maps(static)

    for route in ['route', 'route6']:
        # if there is no route(6) key in the dictionary we can immediately
        # bail out early
        if route not in static:
            continue

        # When leaking routes to other VRFs we must ensure that the destination
        # VRF exists
        for prefix, prefix_options in static[route].items():
            # both the interface and next-hop CLI node can have a VRF subnode,
            # thus we check this using a for loop
            for type in ['interface', 'next_hop']:
                if type in prefix_options:
                    for interface, interface_config in prefix_options[type].items():
                        verify_vrf(interface_config)

            if {'blackhole', 'reject'} <= set(prefix_options):
                raise ConfigError(f'Can not use both blackhole and reject for '\
                                  'prefix "{prefix}"!')

    return None

def generate(static):
    if not static:
        return None

    # Put routing table names in /etc/iproute2/rt_tables
    render(config_file, 'iproute2/static.conf.j2', static)
    static['new_frr_config'] = render_to_string('frr/staticd.frr.j2', static)
    return None

def apply(static):
    static_daemon = 'staticd'

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()
    frr_cfg.load_configuration(static_daemon)

    if 'vrf' in static:
        vrf = static['vrf']
        frr_cfg.modify_section(f'^vrf {vrf}', stop_pattern='^exit-vrf', remove_stop_mark=True)
    else:
        frr_cfg.modify_section(r'^ip route .*')
        frr_cfg.modify_section(r'^ipv6 route .*')

    if 'new_frr_config' in static:
        frr_cfg.add_before(frr.default_add_before, static['new_frr_config'])
    frr_cfg.commit_configuration(static_daemon)

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
