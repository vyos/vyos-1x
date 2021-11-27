#!/usr/bin/env python3
#
# Copyright (C) 2020-2021 VyOS maintainers and contributors
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

from sys import argv
from sys import exit

from vyos.config import Config
from vyos.template import render_to_string
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

frr_daemon = 'zebra'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['vrf']
    vrf = conf.get_config_dict(base, get_first_key=True)
    return vrf

def verify(vrf):
    return None

def generate(vrf):
    vrf['new_frr_config'] = render_to_string('frr/vrf-vni.frr.tmpl', vrf)
    return None

def apply(vrf):
    # add configuration to FRR
    frr_cfg = frr.FRRConfig()
    frr_cfg.load_configuration(frr_daemon)
    frr_cfg.modify_section(f'^vrf .+$', '')
    frr_cfg.add_before(r'(interface .*|line vty|end)', vrf['new_frr_config'])
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
