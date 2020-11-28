#!/usr/bin/env python3
#
# Copyright (C) 2016-2020 VyOS maintainers and contributors
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

import json

from jinja2 import Template
from sys import exit
from vyos.util import popen, DEVNULL

OUT_TMPL_SRC = """
{% if cpu %}
{% if 'vendor' in cpu %}CPU Vendor:       {{cpu.vendor}}{% endif %}
{% if 'model' in cpu %}Model:            {{cpu.model}}{% endif %}
{% if 'cpus' in cpu %}Total CPUs:       {{cpu.cpus}}{% endif %}
{% if 'sockets' in cpu %}Sockets:          {{cpu.sockets}}{% endif %}
{% if 'cores' in cpu %}Cores:            {{cpu.cores}}{% endif %}
{% if 'threads' in cpu %}Threads:          {{cpu.threads}}{% endif %}
{% if 'mhz' in cpu %}Current MHz:      {{cpu.mhz}}{% endif %}
{% if 'mhz_min' in cpu %}Minimum MHz:      {{cpu.mhz_min}}{% endif %}
{% if 'mhz_max' in cpu %}Maximum MHz:      {{cpu.mhz_max}}{% endif %}
{% endif %}
"""

cpu = {}
cpu_json, code = popen('lscpu -J', stderr=DEVNULL)

if code == 0:
    cpu_info = json.loads(cpu_json)
    if len(cpu_info) > 0 and 'lscpu' in cpu_info:
        for prop in cpu_info['lscpu']:
            if (prop['field'].find('Thread(s)') > -1): cpu['threads'] = prop['data']
            if (prop['field'].find('Core(s)')) > -1: cpu['cores'] = prop['data']
            if (prop['field'].find('Socket(s)')) > -1: cpu['sockets'] = prop['data']
            if (prop['field'].find('CPU(s):')) > -1: cpu['cpus'] = prop['data']
            if (prop['field'].find('CPU MHz')) > -1: cpu['mhz'] = prop['data']
            if (prop['field'].find('CPU min MHz')) > -1: cpu['mhz_min'] = prop['data']
            if (prop['field'].find('CPU max MHz')) > -1: cpu['mhz_max'] = prop['data']
            if (prop['field'].find('Vendor ID')) > -1: cpu['vendor'] = prop['data']
            if (prop['field'].find('Model name')) > -1: cpu['model'] = prop['data']

if len(cpu) > 0:
    tmp = { 'cpu':cpu }
    tmpl = Template(OUT_TMPL_SRC)
    print(tmpl.render(tmp))
    exit(0)
else:
    print('CPU information could not be determined\n')
    exit(1)
