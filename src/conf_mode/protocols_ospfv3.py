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
from vyos.configdict import dict_merge
from vyos.configverify import verify_common_route_maps
from vyos.template import render_to_string
from vyos.ifconfig import Interface
from vyos.xml import defaults
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

frr_daemon = 'ospf6d'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['protocols', 'ospfv3']
    ospfv3 = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # Bail out early if configuration tree does not exist
    if not conf.exists(base):
        return ospfv3

    # We also need some additional information from the config, prefix-lists
    # and route-maps for instance. They will be used in verify().
    #
    # XXX: one MUST always call this without the key_mangling() option! See
    # vyos.configverify.verify_common_route_maps() for more information.
    tmp = conf.get_config_dict(['policy'])
    # Merge policy dict into "regular" config dict
    ospfv3 = dict_merge(tmp, ospfv3)

    return ospfv3

def verify(ospfv3):
    if not ospfv3:
        return None

    verify_common_route_maps(ospfv3)

    if 'interface' in ospfv3:
        for ifname, if_config in ospfv3['interface'].items():
            if 'ifmtu' in if_config:
                mtu = Interface(ifname).get_mtu()
                if int(if_config['ifmtu']) > int(mtu):
                    raise ConfigError(f'OSPFv3 ifmtu can not exceed physical MTU of "{mtu}"')

    return None

def generate(ospfv3):
    if not ospfv3:
        ospfv3['new_frr_config'] = ''
        return None

    ospfv3['new_frr_config'] = render_to_string('frr/ospf6d.frr.tmpl', ospfv3)
    return None

def apply(ospfv3):
    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()
    frr_cfg.load_configuration(frr_daemon)
    frr_cfg.modify_section(r'^interface \S+', '')
    frr_cfg.modify_section('^router ospf6$', '')
    frr_cfg.add_before(frr.default_add_before, ospfv3['new_frr_config'])
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
