#!/usr/bin/env python3
#
# Copyright (C) 2016-2024 VyOS maintainers and contributors
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
#    Displays image version and system information.
#    Used by the "run show version" command.

import sys
import typing

import vyos.opmode
import vyos.version
import vyos.limericks

from jinja2 import Template

version_output_tmpl = """
Version:          VyOS {{version}}
Release train:    {{release_train}}
Release flavor:   {{flavor}}

Built by:         {{built_by}}
Built on:         {{built_on}}
Build UUID:       {{build_uuid}}
Build commit ID:  {{build_git}}
{%- if build_comment %}
Build comment:    {{build_comment}}
{% endif %}

Architecture:     {{system_arch}}
Boot via:         {{boot_via}}
System type:      {{system_type}}

Hardware vendor:  {{hardware_vendor}}
Hardware model:   {{hardware_model}}
Hardware S/N:     {{hardware_serial}}
Hardware UUID:    {{hardware_uuid}}

Copyright:        VyOS maintainers and contributors
{%- if limerick %}
{{limerick}}
{% endif -%}
"""

def _get_raw_data(funny=False):
    version_data = vyos.version.get_full_version_data()

    if funny:
        version_data["limerick"] = vyos.limericks.get_random()

    return version_data

def _get_formatted_output(version_data):
    tmpl = Template(version_output_tmpl)
    return tmpl.render(version_data).strip()

def show(raw: bool, funny: typing.Optional[bool]):
    """ Display neighbor table contents """
    version_data = _get_raw_data(funny=funny)

    if raw:
        return version_data
    else:
        return _get_formatted_output(version_data)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)

