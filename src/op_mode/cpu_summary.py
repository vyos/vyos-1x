#!/usr/bin/env python3

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
