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

from vyos.config import Config
from vyos.template import render_to_string
from vyos.util import call
from vyos.configverify import verify_route_maps
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
    base = ['protocols', 'static']
    static = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    return static

def verify(static):
    verify_route_maps(static)
    return None

def generate(static):
    static['new_frr_config'] = render_to_string('frr/static.frr.tmpl', static)
    return None

def apply(static):
    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()
    frr_cfg.load_configuration(frr_daemon)
    frr_cfg.modify_section(r'^ip route .*', '')
    frr_cfg.modify_section(r'^ipv6 route .*', '')
    frr_cfg.add_before(r'(interface .*|line vty)', static['new_frr_config'])
    frr_cfg.commit_configuration(frr_daemon)

    # If FRR config is blank, rerun the blank commit x times due to frr-reload
    # behavior/bug not properly clearing out on one commit.
    if static['new_frr_config'] == '':
        for a in range(5):
            frr_cfg.commit_configuration(frr_daemon)

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
