#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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
#     Provides commands for retrieving information about kernel modules.

import sys
import typing

import vyos.opmode


lsmod_tmpl = """
{% for m in modules -%}
Module: {{m.name}}

{% if m.holders -%}
Holders: {{m.holders | join(", ")}}
{%- endif %}

{% if m.drivers -%}
Drivers: {{m.drivers | join(", ")}}
{%- endif %}

{% for k in m.fields -%}
{{k}}: {{m["fields"][k]}}
{% endfor %}
{% if m.parameters %}

Parameters:

{% for p in m.parameters -%}
{{p}}: {{m["parameters"][p]}}
{% endfor -%}
{% endif -%}

-------------

{% endfor %}
"""

def _get_raw_data(module=None):
    from vyos.utils.kernel import get_module_data, lsmod

    if module:
        return [get_module_data(module)]
    else:
        return lsmod()

def show(raw: bool, module: typing.Optional[str]):
    from jinja2 import Template

    data = _get_raw_data(module=module)

    if raw:
        return data
    else:
        t = Template(lsmod_tmpl)
        output = t.render({"modules": data})
        return output

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
