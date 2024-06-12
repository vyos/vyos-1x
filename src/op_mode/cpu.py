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

import sys

import vyos.opmode
from vyos.utils.cpu import get_cpus
from vyos.utils.cpu import get_core_count

from jinja2 import Template

cpu_template = Template("""
{% for cpu in cpus %}
{% if 'physical id' in cpu %}CPU socket: {{cpu['physical id']}}{% endif %}
{% if 'vendor_id' in cpu %}CPU Vendor:       {{cpu['vendor_id']}}{% endif %}
{% if 'model name' in cpu %}Model:            {{cpu['model name']}}{% endif %}
{% if 'cpu cores' in cpu %}Cores:            {{cpu['cpu cores']}}{% endif %}
{% if 'cpu MHz' in cpu %}Current MHz:      {{cpu['cpu MHz']}}{% endif %}
{% endfor %}
""")

cpu_summary_template = Template("""
Physical CPU cores: {{count}}
CPU model(s): {{models | join(", ")}}
""")

def _get_raw_data():
    return get_cpus()

def _format_cpus(cpu_data):
    env = {'cpus': cpu_data}
    return cpu_template.render(env).strip()

def _get_summary_data():
    count = get_core_count()
    cpu_data = get_cpus()
    models = [c['model name'] for c in cpu_data]
    env = {'count': count, "models": models}

    return env

def _format_cpu_summary(summary_data):
    return cpu_summary_template.render(summary_data).strip()

def show(raw: bool):
    cpu_data = _get_raw_data()

    if raw:
        return cpu_data
    else:
        return _format_cpus(cpu_data)

def show_summary(raw: bool):
    cpu_summary_data = _get_summary_data()

    if raw:
        return cpu_summary_data
    else:
        return _format_cpu_summary(cpu_summary_data)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
