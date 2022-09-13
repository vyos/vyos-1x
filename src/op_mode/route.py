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
#    Displays routing table information.
#    Used by the "run <ip|ipv6> route *" commands.

import re
import sys
import typing

from jinja2 import Template

import vyos.opmode

frr_command_template = Template("""
{% if family == "inet" %}
    show ip route
{% else %}
    show ipv6 route
{% endif %}

{% if table %}
    table {{table}}
{% endif %}

{% if vrf %}
    vrf {{table}}
{% endif %}

{% if tag %}
    tag {{tag}}
{% elif net %}
    {{net}}
{% elif protocol %}
    {{protocol}}
{% endif %}

{% if raw %}
    json
{% endif %}
""")

def show(raw: bool,
         family: str,
         net: typing.Optional[str],
         table: typing.Optional[int],
         protocol: typing.Optional[str],
         vrf: typing.Optional[str],
         tag: typing.Optional[str]):
    if net and protocol:
        raise ValueError("net and protocol are mutually exclusive")
    elif table and vrf:
        raise ValueError("table and vrf are mutually exclusive")
    elif (family == 'inet6') and (protocol == 'rip'):
        raise ValueError("rip is not a valid protocol for family inet6")
    elif (family == 'inet') and (protocol == 'ripng'):
        raise ValueError("rip is not a valid protocol for family inet6")
    else:
        if (family == 'inet6') and (protocol == 'ospf'):
            protocol = 'ospf6'

        kwargs = dict(locals())

        frr_command = frr_command_template.render(kwargs)
        frr_command = re.sub(r'\s+', ' ', frr_command)

        from vyos.util import cmd
        output = cmd(f"vtysh -c '{frr_command}'")

        if raw:
            from json import loads
            return loads(output)
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

