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
import os

from vyos.config import Config
from vyos.configverify import has_frr_protocol_in_dict
from vyos.configverify import verify_common_route_maps
from vyos.configverify import verify_vrf
from vyos.frrender import get_dhcp_route_interfaces
from vyos.frrender import get_frrender_dict
from vyos.utils.dict import dict_search
from vyos.xml_ref import default_value
from vyos.utils.file import write_file
from vyos.template import get_dhcp_router
from vyos.template import render
from vyos import ConfigError
from vyos import airbag
from vyos import defaults
airbag.enable()

config_file = '/etc/iproute2/rt_tables.d/vyos-static.conf'
DHCP_HOOK_IFLIST = defaults.static_route_dhcp_interfaces_path

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

    # equivalent of the C foo ? 'a' : 'b' statement
    static = vrf and dict_search(f'vrf.name.{vrf}.protocols.static',
                                 config_dict) or config_dict['static']
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

    # FRR staticd refuses a blackhole or reject route and a next-hop or
    # interface route for the same prefix with the same distance, which only
    # shows up when frr-reload fails after the commit. Routes in a table are
    # checked as well, blackhole and reject at once is refused there too.
    def route_distance(base, route, prefix, node, config, name=None):
        # the default distance comes from the CLI definition, a tag node needs
        # a value in the path. Compare the numbers, the validator accepts
        # leading zeros.
        path = base + [route, prefix, node]
        if name:
            path.append(name)
        distance = config.get('distance', default_value(path + ['distance']))
        return int(distance)

    def generated_defaults(route, prefix):
        # same conditions and distances as the default routes in staticd.frr.j2
        if route == 'route' and prefix == '0.0.0.0/0':
            for name, config in static.get('dhcp', {}).items():
                # the template renders the route only when a gateway is known,
                # an existing configuration that conflicts before that keeps
                # loading
                if get_dhcp_router(name) is None:
                    continue
                if 'no_default_route' not in config.get('dhcp_options', {}):
                    distance = dict_search(
                        'dhcp_options.default_route_distance', config
                    )
                    yield 'DHCP', name, int(distance or 1)
        if (route, prefix) in [('route', '0.0.0.0/0'), ('route6', '::/0')]:
            for name, config in static.get('pppoe', {}).items():
                if 'no_default_route' in config:
                    continue
                if route == 'route6' and 'ipv6' not in config:
                    continue
                yield 'PPPoE', name, int(config.get('default_route_distance') or 1)

    # the CLI path of the routes, a table or a VRF changes it
    static_base = ['protocols', 'static']
    if vrf:
        static_base = ['vrf', 'name', vrf] + static_base
    sources = [(static_base, static)]
    for table, table_config in static.get('table', {}).items():
        sources.append((static_base + ['table', table], table_config))

    for base, source in sources:
        for route in ['route', 'route6']:
            for prefix, prefix_options in source.get(route, {}).items():
                # a disabled route is not rendered, so it does not conflict
                if all(
                    discard in prefix_options
                    and 'disable' not in prefix_options[discard]
                    for discard in ['blackhole', 'reject']
                ):
                    raise ConfigError(
                        f'Cannot use both blackhole and reject for '
                        f'prefix "{prefix}"!'
                    )

                for discard in ['blackhole', 'reject']:
                    if discard not in prefix_options:
                        continue
                    if 'disable' in prefix_options[discard]:
                        continue
                    discard_distance = route_distance(
                        base, route, prefix, discard, prefix_options[discard]
                    )
                    for type in ['interface', 'next_hop']:
                        node = type.replace('_', '-')
                        for name, config in prefix_options.get(type, {}).items():
                            if 'disable' in config:
                                continue
                            if (
                                route_distance(base, route, prefix, node, config, name)
                                == discard_distance
                            ):
                                raise ConfigError(
                                    f'Cannot use {discard} and {node} "{name}" '
                                    f'with the same distance {discard_distance} '
                                    f'for prefix "{prefix}"!'
                                )

                    # The default routes of DHCP and PPPoE interfaces are
                    # rendered into the same prefix. A commit that changes only
                    # such an interface does not run this check, frr-reload
                    # refuses it and the commit is rolled back.
                    if base == static_base:
                        for kind, name, distance in generated_defaults(route, prefix):
                            if distance == discard_distance:
                                raise ConfigError(
                                    f'Cannot use {discard} and the default route '
                                    f'of {kind} interface "{name}" with the same '
                                    f'distance {distance} for prefix "{prefix}"!'
                                )

                    # A dhcp-interface route has no distance option, it is
                    # rendered like a next-hop route without a distance as soon
                    # as the interface has a gateway
                    if discard_distance == route_distance(
                        base, route, prefix, 'next-hop', {}, 'dhcp'
                    ):
                        for name in prefix_options.get('dhcp_interface', []):
                            raise ConfigError(
                                f'Cannot use {discard} and dhcp-interface "{name}" '
                                f'with the same distance {discard_distance} for '
                                f'prefix "{prefix}"!'
                            )

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

    # equivalent of the C foo ? 'a' : 'b' statement
    static = vrf and dict_search(f'vrf.name.{vrf}.protocols.static',
                                 config_dict) or config_dict['static']

    # Collect interfaces that have DHCP configuration for DHCP hooks. This must
    # be derived from the entire config_dict and not from the (possibly
    # VRF-narrowed) static dict above, as DHCP_HOOK_IFLIST is a single global
    # file - a per VRF invocation would otherwise clobber the list.
    dhcp_interfaces = get_dhcp_route_interfaces(config_dict)

    # Write the interface list for DHCP hooks or clean up if empty
    if dhcp_interfaces:
        write_file(DHCP_HOOK_IFLIST, " ".join(dhcp_interfaces))
    elif os.path.exists(DHCP_HOOK_IFLIST):
        os.unlink(DHCP_HOOK_IFLIST)

    # Put routing table names in /etc/iproute2/rt_tables
    render(config_file, 'iproute2/static.conf.j2', static)

    return None

def apply(config_dict):
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
