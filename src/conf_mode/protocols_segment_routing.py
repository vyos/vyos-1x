#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['protocols', 'segment-routing']
    sr = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True, no_tag_node_value_mangle=True)

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    sr = conf.merge_defaults(sr, recursive=True)

    return sr

def verify(static):
    return None

def generate(static):
    if not static:
        return None

    static['new_frr_config'] = render_to_string('frr/zebra.segment_routing.frr.j2', static)
    return None

def apply(static):
    zebra_daemon = 'zebra'

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()
    frr_cfg.load_configuration(zebra_daemon)
    frr_cfg.modify_section(r'^segment-routing')
    if 'new_frr_config' in static:
        frr_cfg.add_before(frr.default_add_before, static['new_frr_config'])
    frr_cfg.commit_configuration(zebra_daemon)

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
