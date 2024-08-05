#!/usr/bin/env python3
#
# Copyright (C) 2020-2024 VyOS maintainers and contributors
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


from ipaddress import IPv4Address
from sys import exit

from vyos import ConfigError
from vyos import frr
from vyos.config import Config
from vyos.template import render_to_string

from vyos import airbag
airbag.enable()

config_file = r'/tmp/static_mcast.frr'

# Get configuration for static multicast route
def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    mroute = {
        'old_mroute' : {},
        'mroute' : {}
    }

    base_path = "protocols static multicast"

    if not (conf.exists(base_path) or conf.exists_effective(base_path)):
        return None

    conf.set_level(base_path)

    # Get multicast effective routes
    for route in conf.list_effective_nodes('route'):
        mroute['old_mroute'][route] = {}
        for next_hop in conf.list_effective_nodes('route {0} next-hop'.format(route)):
            mroute['old_mroute'][route].update({
                next_hop : conf.return_value('route {0} next-hop {1} distance'.format(route, next_hop))
            })

    # Get multicast effective interface-routes
    for route in conf.list_effective_nodes('interface-route'):
        if not route in  mroute['old_mroute']:
            mroute['old_mroute'][route] = {}
        for next_hop in conf.list_effective_nodes('interface-route {0} next-hop-interface'.format(route)):
            mroute['old_mroute'][route].update({
                next_hop : conf.return_value('interface-route {0} next-hop-interface {1} distance'.format(route, next_hop))
            })

    # Get multicast routes
    for route in conf.list_nodes('route'):
        mroute['mroute'][route] = {}
        for next_hop in conf.list_nodes('route {0} next-hop'.format(route)):
            mroute['mroute'][route].update({
                next_hop : conf.return_value('route {0} next-hop {1} distance'.format(route, next_hop))
            })

    # Get multicast interface-routes
    for route in conf.list_nodes('interface-route'):
        if not route in  mroute['mroute']:
            mroute['mroute'][route] = {}
        for next_hop in conf.list_nodes('interface-route {0} next-hop-interface'.format(route)):
            mroute['mroute'][route].update({
                next_hop : conf.return_value('interface-route {0} next-hop-interface {1} distance'.format(route, next_hop))
            })

    return mroute

def verify(mroute):
    if mroute is None:
        return None

    for route in mroute['mroute']:
        route = route.split('/')
        if IPv4Address(route[0]) < IPv4Address('224.0.0.0'):
            raise ConfigError(route + " not a multicast network")


def generate(mroute):
    if mroute is None:
        return None

    mroute['new_frr_config'] = render_to_string('frr/static_mcast.frr.j2', mroute)
    return None


def apply(mroute):
    if mroute is None:
        return None
    static_daemon = 'staticd'

    frr_cfg = frr.FRRConfig()
    frr_cfg.load_configuration(static_daemon)

    if 'old_mroute' in mroute:
        for route_gr in mroute['old_mroute']:
            for nh in mroute['old_mroute'][route_gr]:
                if mroute['old_mroute'][route_gr][nh]:
                    frr_cfg.modify_section(f'^ip mroute {route_gr} {nh} {mroute["old_mroute"][route_gr][nh]}')
                else:
                    frr_cfg.modify_section(f'^ip mroute {route_gr} {nh}')

    if 'new_frr_config' in mroute:
        frr_cfg.add_before(frr.default_add_before, mroute['new_frr_config'])

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
