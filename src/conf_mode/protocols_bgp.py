#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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
from vyos.util import call
from vyos.template import render
from vyos.template import render_to_string
from vyos import frr
from vyos import ConfigError, airbag
airbag.enable()

config_file = r'/tmp/bgp.frr'

def get_config():
    conf = Config()
    base = ['protocols', 'nbgp']
    bgp = conf.get_config_dict(base, key_mangling=('-', '_'))
    if not conf.exists(base):
        return None

    from pprint import pprint
    pprint(bgp)

    return bgp

def verify(bgp):
    if not bgp:
        return None

    return None

def generate(bgp):
    if not bgp:
        return None

    # render(config) not needed, its only for debug
    render(config_file, 'frr/bgp.frr.tmpl', bgp)

    bgp['new_frr_config'] = render_to_string('frr/bgp.frr.tmpl', bgp)

    return None

def apply(bgp):
    if bgp is None:
        return None

    # Save original configration prior to starting any commit actions
    bgp['original_config'] = frr.get_configuration(daemon='bgpd')
    bgp['modified_config'] = frr.replace_section(bgp['original_config'], bgp['new_frr_config'], from_re='router bgp .*')

    # Debugging
    print('--------- DEBUGGING ----------')
    print(f'Existing config:\n{bgp["original_config"]}\n\n')
    print(f'Replacement config:\n{bgp["new_frr_config"]}\n\n')
    print(f'Modified config:\n{bgp["modified_config"]}\n\n')

    # Frr Mark configuration will test for syntax errors and exception out if any syntax errors are detected
    frr.mark_configuration(bgp['modified_config'])

    # Commit the resulting new configuration to frr, this will render an frr.CommitError() Exception on fail
    frr.reload_configuration(bgp['modified_config'], daemon='bgpd')

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
