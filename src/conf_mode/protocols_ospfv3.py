#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.configverify import verify_common_route_maps
from vyos.configverify import verify_route_map
from vyos.configverify import verify_interface_exists
from vyos.configverify import has_frr_protocol_in_dict
from vyos.frrender import FRRender
from vyos.frrender import get_frrender_dict
from vyos.ifconfig import Interface
from vyos.utils.dict import dict_search
from vyos.utils.network import get_interface_config
from vyos.utils.process import is_systemd_service_running
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    return get_frrender_dict(conf, argv)

def verify(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'ospfv3'):
        return None

    vrf = None
    if 'vrf_context' in config_dict:
        vrf = config_dict['vrf_context']

    # eqivalent of the C foo ? 'a' : 'b' statement
    ospfv3 = vrf and dict_search(f'vrf.name.{vrf}.protocols.ospfv3',
                                 config_dict) or config_dict['ospfv3']
    ospfv3['policy'] = config_dict['policy']

    verify_common_route_maps(ospfv3)

    # As we can have a default-information route-map, we need to validate it!
    route_map_name = dict_search('default_information.originate.route_map', ospfv3)
    if route_map_name: verify_route_map(route_map_name, ospfv3)

    if 'area' in ospfv3:
        for area, area_config in ospfv3['area'].items():
            if 'area_type' in area_config:
                if len(area_config['area_type']) > 1:
                    raise ConfigError(f'Can only configure one area-type for OSPFv3 area "{area}"!')
            if 'range' in area_config:
                for range, range_config in area_config['range'].items():
                    if {'not_advertise', 'advertise'} <= range_config.keys():
                        raise ConfigError(f'"not-advertise" and "advertise" for "range {range}" cannot be both configured at the same time!')

    if 'interface' in ospfv3:
        for interface, interface_config in ospfv3['interface'].items():
            verify_interface_exists(ospfv3, interface)
            if 'ifmtu' in interface_config:
                mtu = Interface(interface).get_mtu()
                if int(interface_config['ifmtu']) > int(mtu):
                    raise ConfigError(f'OSPFv3 ifmtu can not exceed physical MTU of "{mtu}"')

            # If interface specific options are set, we must ensure that the
            # interface is bound to our requesting VRF. Due to the VyOS
            # priorities the interface is bound to the VRF after creation of
            # the VRF itself, and before any routing protocol is configured.
            if vrf:
                tmp = get_interface_config(interface)
                if 'master' not in tmp or tmp['master'] != vrf:
                    raise ConfigError(f'Interface "{interface}" is not a member of VRF "{vrf}"!')

    return None

def generate(config_dict):
    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().generate(config_dict)
    return None

def apply(config_dict):
    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().apply()
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
