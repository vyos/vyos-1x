#!/usr/bin/env python3

import re
import os
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--regex', action='append')
parser.add_argument('--exec', action='append')
parser.add_argument('--value', action='store')

args = parser.parse_args()

debug = False

# Multiple arguments work like logical OR

try:
    for r in args.regex:
        if re.match(r, args.value):
            sys.exit(0)
except Exception as exn:
    if debug:
        print(exn)
    else:        
        pass

try:
    for cmd in args.exec:
        cmd = "{0} {1}".format(cmd, args.value)
        if debug:
            print(cmd)
        res = os.system(cmd)
        if res == 0:
            sys.exit(0)
except Exception as exn:
    if debug:
        print(exn)
    else:
        pass

sys.exit(1)
