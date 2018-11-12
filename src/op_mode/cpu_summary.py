#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
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

import re
from vyos.util import colon_separated_to_dict

FILE_NAME = '/proc/cpuinfo'

with open(FILE_NAME, 'r') as f:
    data_raw = f.read()

data = colon_separated_to_dict(data_raw)

# Accumulate all data in a dict for future support for machine-readable output
cpu_data = {}
cpu_data['cpu_number'] = len(data['processor'])
cpu_data['models'] = list(set(data['model name']))

# Strip extra whitespace from CPU model names, /proc/cpuinfo is prone to that
cpu_data['models'] = map(lambda s: re.sub(r'\s+', ' ', s), cpu_data['models'])

print("CPU(s): {0}".format(cpu_data['cpu_number']))
print("CPU model(s): {0}".format(",".join(cpu_data['models'])))
