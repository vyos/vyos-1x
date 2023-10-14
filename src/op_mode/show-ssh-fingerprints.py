#!/usr/bin/env python3
#
# Copyright 2017-2023 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import sys
import glob
import argparse
from vyos.utils.process import cmd

# Parse command line
parser = argparse.ArgumentParser()
parser.add_argument("--ascii", help="Show visual ASCII art representation of the public key", action="store_true")
args = parser.parse_args()

# Get list of server public keys
publickeys = glob.glob("/etc/ssh/*.pub")

if publickeys:
    print("SSH server public key fingerprints:\n", flush=True)
    for keyfile in publickeys:
        if args.ascii:
            try:
                print(cmd("ssh-keygen -l -v -E sha256 -f " + keyfile) + "\n", flush=True)
            # Ignore invalid public keys
            except:
                pass
        else:
            try:
                print(cmd("ssh-keygen -l -E sha256 -f " + keyfile) + "\n", flush=True)
            # Ignore invalid public keys
            except:
                pass
else:
    print("No SSH server public keys are found.", flush=True)

sys.exit(0)
