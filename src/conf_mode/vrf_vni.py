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

from sys import argv
from sys import exit

from vyos.config import Config
from vyos.template import render_to_string
from vyos.util import dict_search
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    vrf_name = None
    if len(argv) > 1:
        vrf_name = argv[1]
    else:
        return None

    # Using duplicate L3VNIs makes no sense - it's also forbidden in FRR,
    # thus VyOS CLI must deny this, too. Instead of getting only the dict for
    # the requested VRF and den comparing it with depenent VRfs to not have any
    # duplicate we will just grad ALL VRFs by default but only render/apply
    # the configuration for the requested VRF - that makes the code easier and
    # hopefully less error prone
    vrf = conf.get_config_dict(['vrf'], key_mangling=('-', '_'),
                               no_tag_node_value_mangle=True,
                               get_first_key=True)

    # Store name of VRF we are interested in for FRR config rendering
    vrf.update({'only_vrf' : vrf_name})

    return vrf

def verify(vrf):
    if not vrf:
        return

    if len(argv) < 2:
        raise ConfigError('VRF parameter not specified when valling vrf_vni.py')

    if 'name' in vrf:
        vni_ids = []
        for name, vrf_config in vrf['name'].items():
            # VRF VNI (Virtual Network Identifier) must be unique on the system
            if 'vni' in vrf_config:
                if vrf_config['vni'] in vni_ids:
                    raise ConfigError(f'VRF "{name}" VNI is not unique!')
                vni_ids.append(vrf_config['vni'])

    return None

def generate(vrf):
    if not vrf:
        return

    vrf['new_frr_config'] = render_to_string('frr/zebra.vrf.route-map.frr.j2', vrf)
    return None

def apply(vrf):
    frr_daemon = 'zebra'

    # add configuration to FRR
    frr_cfg = frr.FRRConfig()
    frr_cfg.load_configuration(frr_daemon)
    # There is only one VRF inside the dict as we read only one in get_config()
    if vrf and 'only_vrf' in vrf:
        vrf_name = vrf['only_vrf']
        frr_cfg.modify_section(f'^vrf {vrf_name}', stop_pattern='^exit-vrf', remove_stop_mark=True)
    if vrf and 'new_frr_config' in vrf:
        frr_cfg.add_before(frr.default_add_before, vrf['new_frr_config'])
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
