#!/usr/bin/env python3

# Extract the list of interfaces available for traffic dumps from tcpdump -D

import re
import subprocess

if __name__ == '__main__':
    out = subprocess.check_output(['/usr/sbin/tcpdump', '-D']).decode().strip()
    out = out.split("\n")

    intfs = " ".join(map(lambda s: re.search(r'\d+\.(\S+)\s', s).group(1), out))

    print(intfs)
