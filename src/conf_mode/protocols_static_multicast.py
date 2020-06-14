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

import jinja2
import copy
import os
import vyos.validate
from ipaddress import IPv4Address
from sys import exit

from vyos import ConfigError
from vyos.config import Config

config_file = r'/tmp/static_mcast.frr'

config_tmpl = """
!
{% for route_gr in old_mroute -%}
{% for nh in old_mroute[route_gr] -%}
{% if old_mroute[route_gr][nh] -%}
no ip mroute {{ route_gr }} {{ nh }} {{ old_mroute[route_gr][nh] }}
{% else -%}
no ip mroute {{ route_gr }} {{ nh }}
{% endif -%}
{% endfor -%}
{% endfor -%}
{% for route_gr in mroute -%}
{% for nh in mroute[route_gr] -%}
{% if mroute[route_gr][nh] -%}
ip mroute {{ route_gr }} {{ nh }} {{ mroute[route_gr][nh] }}
{% else -%}
ip mroute {{ route_gr }} {{ nh }}
{% endif -%}
{% endfor -%}
{% endfor -%}
!
"""

# Get configuration for static multicast route
def get_config():
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
        route_lst = route.split('/')
        if IPv4Address(route_lst[0]) < IPv4Address('224.0.0.0'):
            raise ConfigError(route + " not a multicast network")

def generate(mroute):
    if mroute is None:
        return None

    tmpl = jinja2.Template(config_tmpl)
    config_text = tmpl.render(mroute)
    with open(config_file, 'w') as f:
        f.write(config_text)

    return None

def apply(mroute):
    if mroute is None:
        return None

    if os.path.exists(config_file):
        os.system("sudo vtysh -d staticd -f " + config_file)
        os.remove(config_file)

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
