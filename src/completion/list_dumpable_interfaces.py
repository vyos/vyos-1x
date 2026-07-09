#!/usr/bin/env python3

# Extract the list of interfaces available for traffic dumps from tcpdump -D

import re

from vyos.utils.process import cmdl

if __name__ == '__main__':
    out = cmdl(['tcpdump', '-D']).split('\n')
    intfs = " ".join(map(lambda s: re.search(r'\d+\.(\S+)\s', s).group(1), out))
    print(intfs)
