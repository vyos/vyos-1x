#!/usr/bin/env python3

import sys
import json
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--file', default='data/config-sync-exclude.json')
parser.add_argument('--paths', nargs='+')

args = parser.parse_args()
paths = args.paths
file = args.file

try:
    with open(file) as f:
        exclude_str = json.load(f)
except FileNotFoundError:
    print(f'Adding new file: {file}')
    exclude_str = []
except json.JSONDecodeError as e:
    sys.exit(e)

for path in (paths or []):
    exclude_str.append(path.split())

with open(file, 'w') as f:
    json.dump(exclude_str, f, indent=1)
    f.write('\n')
