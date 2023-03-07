#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Purpose:
#    Displays bgp neighbors information.
#    Used by the "show bgp (vrf <tag>) ipv4|ipv6 neighbors" commands.

import re
import sys
import typing

import jmespath
from jinja2 import Template
from humps import decamelize

from vyos.configquery import ConfigTreeQuery

import vyos.opmode

ArgFamily = typing.Literal['inet', 'inet6']

frr_command_template = Template("""
{% if family %}
    show bgp
        {{ 'vrf ' ~ vrf if vrf else '' }}
        {{ 'ipv6' if family == 'inet6' else 'ipv4'}}
        {{ 'neighbor ' ~ peer if peer else 'summary' }}
{% endif %}

{% if raw %}
    json
{% endif %}
""")


def _verify(func):
    """Decorator checks if BGP config exists
    BGP configuration can be present under vrf <tag>
    If we do npt get arg 'peer' then it can be 'bgp summary'
    """
    from functools import wraps

    @wraps(func)
    def _wrapper(*args, **kwargs):
        config = ConfigTreeQuery()
        afi = 'ipv6' if kwargs.get('family') == 'inet6' else 'ipv4'
        global_vrfs = ['all', 'default']
        peer = kwargs.get('peer')
        vrf = kwargs.get('vrf')
        unconf_message = f'BGP or neighbor is not configured'
        # Add option to check the specific neighbor if we have arg 'peer'
        peer_opt = f'neighbor {peer} address-family {afi}-unicast' if peer else ''
        vrf_opt = ''
        if vrf and vrf not in global_vrfs:
            vrf_opt = f'vrf name {vrf}'
        # Check if config does not exist
        if not config.exists(f'{vrf_opt} protocols bgp {peer_opt}'):
            raise vyos.opmode.UnconfiguredSubsystem(unconf_message)
        return func(*args, **kwargs)

    return _wrapper


@_verify
def show_neighbors(raw: bool,
                   family: ArgFamily,
                   peer: typing.Optional[str],
                   vrf: typing.Optional[str]):
    kwargs = dict(locals())
    frr_command = frr_command_template.render(kwargs)
    frr_command = re.sub(r'\s+', ' ', frr_command)

    from vyos.util import cmd
    output = cmd(f"vtysh -c '{frr_command}'")

    if raw:
        from json import loads
        data = loads(output)
        # Get list of the peers
        peers = jmespath.search('*.peers | [0]', data)
        if peers:
            # Create new dict, delete old key 'peers'
            # add key 'peers' neighbors to the list
            list_peers = []
            new_dict = jmespath.search('* | [0]', data)
            if 'peers' in new_dict:
                new_dict.pop('peers')

                for neighbor, neighbor_options in peers.items():
                    neighbor_options['neighbor'] = neighbor
                    list_peers.append(neighbor_options)
                new_dict['peers'] = list_peers
            return decamelize(new_dict)
        data = jmespath.search('* | [0]', data)
        return decamelize(data)

    else:
        return output


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
