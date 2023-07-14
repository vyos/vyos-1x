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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Purpose:
#    Displays BGP neighbors and tables information.

import re
import sys
import typing

from jinja2 import Template

import vyos.opmode

frr_command_template = Template("""
show bgp

{## VRF and family modifiers that may precede any options ##}

{% if vrf %}
    vrf {{vrf}}
{% endif %}

{% if family == "inet" %}
    ipv4
{% elif family == "inet6" %}
    ipv6
{% elif family == "l2vpn" %}
    l2vpn evpn
{% endif %}

{% if family_modifier == "unicast" %}
    unicast
{% elif family_modifier == "multicast" %}
    multicast
{% elif family_modifier == "flowspec" %}
    flowspec
{% elif family_modifier == "vpn" %}
    vpn
{% endif %}

{## Mutually exclusive query parameters ##}

{# Network prefix #}
{% if prefix %}
    {{prefix}}

    {% if longer_prefixes %}
      longer-prefixes
    {% elif best_path %}
      bestpath
    {% endif %}
{% endif %}

{# Regex #}
{% if regex %}
    regex {{regex}}
{% endif %}

{## Raw modifier ##}

{% if raw %}
    json
{% endif %}
""")

ArgFamily = typing.Literal['inet', 'inet6', 'l2vpn']
ArgFamilyModifier = typing.Literal['unicast', 'labeled_unicast', 'multicast', 'vpn', 'flowspec']

def show_summary(raw: bool):
    from vyos.utils.process import cmd

    if raw:
        from json import loads

        output = cmd(f"vtysh -c 'show bgp summary json'").strip()

        # FRR 8.5 correctly returns an empty object when BGP is not running,
        # we don't need to do anything special here
        return loads(output)
    else:
        output = cmd(f"vtysh -c 'show bgp summary'")
        return output

def show_neighbors(raw: bool):
    from vyos.utils.process import cmd
    from vyos.utils.dict import dict_to_list

    if raw:
        from json import loads

        output = cmd(f"vtysh -c 'show bgp neighbors json'").strip()
        d = loads(output)
        return dict_to_list(d, save_key_to="neighbor")
    else:
        output = cmd(f"vtysh -c 'show bgp neighbors'")
        return output

def show(raw: bool,
         family: ArgFamily,
         family_modifier: ArgFamilyModifier,
         prefix: typing.Optional[str],
         longer_prefixes: typing.Optional[bool],
         best_path: typing.Optional[bool],
         regex: typing.Optional[str],
         vrf: typing.Optional[str]):
    from vyos.utils.dict import dict_to_list

    if (longer_prefixes or best_path) and (prefix is None):
        raise ValueError("longer_prefixes and best_path can only be used when prefix is given")
    elif (family == "l2vpn") and (family_modifier is not None):
        raise ValueError("l2vpn family does not accept any modifiers")
    else:
        kwargs = dict(locals())

        frr_command = frr_command_template.render(kwargs)
        frr_command = re.sub(r'\s+', ' ', frr_command)

        from vyos.utils.process import cmd
        output = cmd(f"vtysh -c '{frr_command}'")

        if raw:
            from json import loads
            d = loads(output)
            if not ("routes" in d):
                raise vyos.opmode.InternalError("FRR returned a BGP table with no routes field")
            d = d["routes"]
            routes = dict_to_list(d, save_key_to="route_key")
            return routes
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
