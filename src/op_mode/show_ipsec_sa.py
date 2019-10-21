#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
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
import sys

import vici
import tabulate
import hurry.filesize

import vyos.util


try:
    session = vici.Session()
    sas = session.list_sas()
except PermissionError:
    print("You do not have a permission to connect to the IPsec daemon")
    sys.exit(1)
except ConnectionRefusedError:
    print("IPsec is not runing")
    sys.exit(1)
except Exception as e:
    print("An error occured: {0}".format(e))
    sys.exit(1)

sa_data = []

for sa in sas:
    # list_sas() returns a list of single-item dicts
    for peer in sa:
        parent_sa = sa[peer]

        if parent_sa["state"] == b"ESTABLISHED":
            state = "up"
        else:
            state = "down"

        if state == "up":
            uptime = vyos.util.seconds_to_human(parent_sa["established"].decode())
        else:
            uptime = "N/A"

        remote_host = parent_sa["remote-host"].decode()
        remote_id = parent_sa["remote-id"].decode()

        if remote_host == remote_id:
            remote_id = "N/A"

        # The counters can only be obtained from the child SAs
        child_sas = parent_sa["child-sas"]
        installed_sas = {k: v for k, v in child_sas.items() if v["state"] == b"INSTALLED"}

        if not installed_sas:
            data = [peer, state, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"]
            sa_data.append(data)
        else:
            for csa in installed_sas:
                isa = installed_sas[csa]

                bytes_in = hurry.filesize.size(int(isa["bytes-in"].decode()))
                bytes_out = hurry.filesize.size(int(isa["bytes-out"].decode()))
                bytes_str = "{0}/{1}".format(bytes_in, bytes_out)

                pkts_in = hurry.filesize.size(int(isa["packets-in"].decode()), system=hurry.filesize.si)
                pkts_out = hurry.filesize.size(int(isa["packets-out"].decode()), system=hurry.filesize.si)
                pkts_str = "{0}/{1}".format(pkts_in, pkts_out)
                # Remove B from <1K values
                pkts_str = re.sub(r'B', r'', pkts_str)

                enc = isa["encr-alg"].decode()
                if "encr-keysize" in isa:
                    key_size = isa["encr-keysize"].decode()
                else:
                    key_size = ""
                if "integ-alg" in isa:
                    hash = isa["integ-alg"].decode()
                else:
                    hash = ""
                if "dh-group" in isa:
                    dh_group = isa["dh-group"].decode()
                else:
                    dh_group = ""

                proposal = enc
                if key_size:
                    proposal = "{0}_{1}".format(proposal, key_size)
                if hash:
                    proposal = "{0}/{1}".format(proposal, hash)
                if dh_group:
                    proposal = "{0}/{1}".format(proposal, dh_group)

                data = [peer, state, uptime, bytes_str, pkts_str, remote_host, remote_id, proposal]
                sa_data.append(data)

headers = ["Connection", "State", "Uptime", "Bytes In/Out", "Packets In/Out", "Remote address", "Remote ID", "Proposal"]
output = tabulate.tabulate(sa_data, headers)
print(output)
