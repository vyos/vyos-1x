#!/usr/bin/env python3
#
# Copyright 2023 VyOS maintainers and contributors <maintainers@vyos.io>
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
import vyos.opmode
from vyos.utils.process import cmd
from vyos.configquery import ConfigTreeQuery
from tabulate import tabulate

def show_fingerprints(raw: bool, ascii: bool):
    config = ConfigTreeQuery()
    if not config.exists("service ssh"):
        raise vyos.opmode.UnconfiguredSubsystem("SSH server is not enabled.")

    publickeys = glob.glob("/etc/ssh/*.pub")

    if publickeys:
        keys = []
        for keyfile in publickeys:
            try:
                if ascii:
                    keydata = cmd("ssh-keygen -l -v -E sha256 -f " + keyfile).splitlines()
                else:
                    keydata = cmd("ssh-keygen -l -E sha256 -f " + keyfile).splitlines()
                type = keydata[0].split(None)[-1].strip("()")
                key_size = keydata[0].split(None)[0]
                fingerprint = keydata[0].split(None)[1]
                comment = keydata[0].split(None)[2:-1][0]
                if ascii:
                    ascii_art = "\n".join(keydata[1:])
                    keys.append({"type": type, "key_size": key_size, "fingerprint": fingerprint, "comment": comment, "ascii_art": ascii_art})
                else:
                    keys.append({"type": type, "key_size": key_size, "fingerprint": fingerprint, "comment": comment})
            except:
                # Ignore invalid public keys
                pass
        if raw:
            return keys
        else:
            headers = {"type": "Type", "key_size": "Key Size", "fingerprint": "Fingerprint", "comment": "Comment", "ascii_art": "ASCII Art"}
            output = "SSH server public key fingerprints:\n\n" + tabulate(keys, headers=headers, tablefmt="simple")
            return output
    else:
        if raw:
            return []
        else:
            return "No SSH server public keys are found."
