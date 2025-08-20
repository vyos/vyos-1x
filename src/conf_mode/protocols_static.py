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

from ipaddress import IPv4Network
from sys import exit
from sys import argv

from vyos.config import Config
from vyos.configverify import has_frr_protocol_in_dict
from vyos.configverify import verify_common_route_maps
from vyos.configverify import verify_vrf
from vyos.frrender import FRRender
from vyos.frrender import get_frrender_dict
from vyos.utils.process import is_systemd_service_running
from vyos.template import render
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = '/etc/iproute2/rt_tables.d/vyos-static.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    return get_frrender_dict(conf, argv)

def verify(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'static'):
        return None

    vrf = None
    if 'vrf_context' in config_dict:
        vrf = config_dict['vrf_context']

    # eqivalent of the C foo ? 'a' : 'b' statement
    static = vrf and config_dict['vrf']['name'][vrf]['protocols']['static'] or config_dict['static']
    static['policy'] = config_dict['policy']

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
                                  f'prefix "{prefix}"!')

    if 'multicast' in static and 'route' in static['multicast']:
        for prefix, prefix_options in static['multicast']['route'].items():
            if not IPv4Network(prefix).is_multicast:
                raise ConfigError(f'{prefix} is not a multicast network!')

    return None

def generate(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'static'):
        return None

    vrf = None
    if 'vrf_context' in config_dict:
        vrf = config_dict['vrf_context']

    # eqivalent of the C foo ? 'a' : 'b' statement
    static = vrf and config_dict['vrf']['name'][vrf]['protocols']['static'] or config_dict['static']

    # Put routing table names in /etc/iproute2/rt_tables
    render(config_file, 'iproute2/static.conf.j2', static)

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
