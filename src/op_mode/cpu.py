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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys

import vyos.opmode
from vyos.utils.cpu import get_core_count

from jinja2 import Template

cpu_template = Template("""
{% for cpu in cpus %}
{% if not loop.first %}

{% endif %}
{% if 'vendor' in cpu %}
CPU Vendor:        {{cpu.vendor}}
{% endif %}
{% if 'model' in cpu %}
Model:             {{cpu.model}}
{% endif %}
{% if 'sockets' in cpu %}
Sockets:           {{cpu.sockets}}
{% endif %}
{% if 'clusters' in cpu %}
Clusters:          {{cpu.clusters}}
{% endif %}
{% if 'cores_per_socket' in cpu %}
Cores per socket:  {{cpu.cores_per_socket}}
{% endif %}
{% if 'cores_per_cluster' in cpu %}
Cores per cluster: {{cpu.cores_per_cluster}}
{% endif %}
{% if 'threads_per_core' in cpu %}
Threads per core:  {{cpu.threads_per_core}}
{% endif %}
{% if 'max_mhz' in cpu %}
Max MHz:           {{cpu.max_mhz}}
{% endif %}
{% if 'min_mhz' in cpu %}
Min MHz:           {{cpu.min_mhz}}
{% endif %}
{% endfor %}
""", trim_blocks=True)

cpu_summary_template = Template("""
Physical CPU cores: {{count}}
CPU model(s): {{models | join(", ")}}
""")

# lscpu summary fields reported per CPU type
lscpu_fields = {
    'Socket(s)': 'sockets',
    'Cluster(s)': 'clusters',
    'Core(s) per socket': 'cores_per_socket',
    'Core(s) per cluster': 'cores_per_cluster',
    'Thread(s) per core': 'threads_per_core',
    'CPU max MHz': 'max_mhz',
    'CPU min MHz': 'min_mhz',
}

def _lscpu_entries(entries):
    for entry in entries:
        yield entry['field'].rstrip(':'), entry['data']
        if 'children' in entry:
            yield from _lscpu_entries(entry['children'])

def _get_raw_data():
    """ Returns one entry per CPU type as reported by lscpu, which - unlike
        /proc/cpuinfo - also knows the vendor and model name of ARM CPUs
    """
    from json import loads
    from vyos.utils.process import cmdl

    cpus = []
    vendor = None
    for field, data in _lscpu_entries(loads(cmdl(['lscpu', '--json']))['lscpu']):
        if data == '-':
            continue
        if field == 'Vendor ID':
            vendor = data
            continue
        # a new CPU type starts with its model name
        if field == 'Model name' or (field in lscpu_fields and not cpus):
            cpus.append({'vendor': vendor} if vendor else {})
        if field == 'Model name':
            cpus[-1]['model'] = data
        elif field in lscpu_fields:
            key = lscpu_fields[field]
            cpus[-1][key] = float(data) if key.endswith('_mhz') else int(data)

    return cpus

def _format_cpus(cpu_data):
    env = {'cpus': cpu_data}
    return cpu_template.render(env).strip()

def _get_summary_data():
    count = get_core_count()
    models = [c.get('model', 'unknown') for c in _get_raw_data()]
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
