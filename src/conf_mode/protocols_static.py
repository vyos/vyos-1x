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
from vyos.configverify import verify_common_route_maps
from vyos.configverify import verify_vrf
from vyos.template import render_to_string
from vyos.util import call
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

frr_daemon = 'staticd'

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
    static = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # Assign the name of our VRF context
    if vrf: static['vrf'] = vrf

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

    return None

def generate(static):
    static['new_frr_config'] = render_to_string('frr/static.frr.tmpl', static)
    return None

def apply(static):
    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()
    frr_cfg.load_configuration(frr_daemon)

    if 'vrf' in static:
        vrf = static['vrf']
        frr_cfg.modify_section(f'^vrf {vrf}$', '')
    else:
        frr_cfg.modify_section(r'^ip route .*', '')
        frr_cfg.modify_section(r'^ipv6 route .*', '')

    frr_cfg.add_before(r'(interface .*|line vty)', static['new_frr_config'])
    frr_cfg.commit_configuration(frr_daemon)

    # If FRR config is blank, rerun the blank commit x times due to frr-reload
    # behavior/bug not properly clearing out on one commit.
    if static['new_frr_config'] == '':
        for a in range(5):
            frr_cfg.commit_configuration(frr_daemon)

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
