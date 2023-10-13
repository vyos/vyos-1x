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
import os

publickeys = glob.glob('/etc/ssh/*.pub')

if publickeys:
    print("SSH server public key fingerprints:\n", flush=True)
    for keyfile in publickeys:
        os.system('ssh-keygen -l -v -E sha256 -f ' + keyfile)
        print("")
else:
    print("No SSH server public keys are found.")

sys.exit(0)
