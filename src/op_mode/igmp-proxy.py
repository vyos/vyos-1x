#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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

# File: show_igmpproxy.py
# Purpose:
#    Display istatistics from IPv4 IGMP proxy.
#    Used by the "run show ip multicast" command tree.

import ipaddress
import json
import socket
import sys
import tabulate

import vyos.config
import vyos.opmode

from vyos.utils.convert import bytes_to_human
from vyos.utils.io import print_error
from vyos.utils.process import process_named_running

def _is_configured():
    """Check if IGMP proxy is configured"""
    return vyos.config.Config().exists_effective('protocols igmp-proxy')

def _kernel_to_ip(addr):
    """
    Convert any given address from Linux kernel to a proper, IPv4 address
    using the correct host byte order.
    """
    # Convert from hex 'FE000A0A' to decimal '4261415434'
    addr = int(addr, 16)
    # Kernel ABI _always_ uses network byte order.
    addr = socket.ntohl(addr)
    return str(ipaddress.IPv4Address(addr))

def _process_mr_vif():
    """Read rows from /proc/net/ip_mr_vif into dicts."""
    result = []
    with open('/proc/net/ip_mr_vif', 'r') as f:
        next(f)
        for line in f:
            result.append({
                'Interface': line.split()[1],
                'PktsIn'   : int(line.split()[3]),
                'PktsOut'  : int(line.split()[5]),
                'BytesIn'  : int(line.split()[2]),
                'BytesOut' : int(line.split()[4]),
                'Local'    : _kernel_to_ip(line.split()[7]),
            })
    return result

def show_interface(raw: bool):
    if data := _process_mr_vif():
        if raw:
            # Make the interface name the key for each row.
            table = {}
            for v in data:
                table[v.pop('Interface')] = v
            return json.loads(json.dumps(table))
        # Make byte values human-readable for the table.
        arr = []
        for x in data:
            arr.append({k: bytes_to_human(v) if k.startswith('Bytes') \
                        else v for k, v in x.items()})
        return tabulate.tabulate(arr, headers='keys')


if not _is_configured():
    print_error('IGMP proxy is not configured.')
    sys.exit(0)
if not process_named_running('igmpproxy'):
    print_error('IGMP proxy is not running.')
    sys.exit(0)


if __name__ == "__main__":
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print_error(e)
        sys.exit(1)
