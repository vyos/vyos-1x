#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
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

import sys
import jinja2
import argparse
import ipaddress
import socket

import vyos.config

# Output Template for "show ip multicast interface" command
#
# Example:
# Interface  BytesIn      PktsIn       BytesOut     PktsOut      Local
# eth0       0.0b         0            0.0b         0            xxx.xxx.xxx.65
# eth1       0.0b         0            0.0b         0            xxx.xxx.xx.201
# eth0.3     0.0b         0            0.0b         0            xxx.xxx.x.7
# tun1       0.0b         0            0.0b         0            xxx.xxx.xxx.2
vif_out_tmpl = """
{%- for r in data %}
{{ "%-10s"|format(r.interface) }} {{ "%-12s"|format(r.bytes_in) }} {{ "%-12s"|format(r.pkts_in) }} {{ "%-12s"|format(r.bytes_out) }} {{ "%-12s"|format(r.pkts_out) }} {{ "%-15s"|format(r.loc) }}
{%- endfor %}
"""

# Output Template for "show ip multicast mfc" command
#
# Example:
# Group             Origin            In    Out           Pkts        Bytes        Wrong
# xxx.xxx.xxx.250   xxx.xx.xxx.75     --
# xxx.xxx.xx.124    xx.xxx.xxx.26     --
mfc_out_tmpl = """
{%- for r in data %}
{{ "%-15s"|format(r.group) }} {{ "%-15s"|format(r.origin) }} {{ "%-12s"|format(r.pkts) }} {{ "%-12s"|format(r.bytes) }} {{ "%-12s"|format(r.wrong) }} {{ "%-10s"|format(r.iif) }} {{ "%-20s"|format(r.oifs|join(', ')) }}
{%- endfor %}
"""

parser = argparse.ArgumentParser()
parser.add_argument("--interface", action="store_true", help="Interface Statistics")
parser.add_argument("--mfc", action="store_true", help="Multicast Forwarding Cache")

def byte_string(size):
    # convert size to integer
    size = int(size)

    # One Terrabyte
    s_TB = 1024 * 1024 * 1024 * 1024
    # One Gigabyte
    s_GB = 1024 * 1024 * 1024
    # One Megabyte
    s_MB = 1024 * 1024
    # One Kilobyte
    s_KB = 1024
    # One Byte
    s_B  = 1

    if size > s_TB:
        return str(round((size/s_TB), 2)) + 'TB'
    elif size > s_GB:
        return str(round((size/s_GB), 2)) + 'GB'
    elif size > s_MB:
        return str(round((size/s_MB), 2)) + 'MB'
    elif size > s_KB:
        return str(round((size/s_KB), 2)) + 'KB'
    else:
        return str(round((size/s_B), 2)) + 'b'

    return None

def kernel2ip(addr):
    """
    Convert any given addr from Linux Kernel to a proper, IPv4 address
    using the correct host byte order.
    """

    # Convert from hex 'FE000A0A' to decimal '4261415434'
    addr = int(addr, 16)
    # Kernel ABI _always_ uses network byteorder
    addr = socket.ntohl(addr)

    return ipaddress.IPv4Address( addr )

def do_mr_vif():
    """
    Read contents of file /proc/net/ip_mr_vif and print a more human
    friendly version to the command line. IPv4 addresses present as
    32bit integers in hex format are converted to IPv4 notation, too.
    """

    with open('/proc/net/ip_mr_vif', 'r') as f:
        lines = len(f.readlines())
        if lines < 2:
            return None

    result = {
        'data': []
    }

    # Build up table format string
    table_format = {
        'interface': 'Interface',
        'pkts_in'  : 'PktsIn',
        'pkts_out' : 'PktsOut',
        'bytes_in' : 'BytesIn',
        'bytes_out': 'BytesOut',
        'loc'      : 'Local'
    }
    result['data'].append(table_format)

    # read and parse information from /proc filesystema
    with open('/proc/net/ip_mr_vif', 'r') as f:
        header_line = next(f)
        for line in f:
            data = {
                'interface': line.split()[1],
                'pkts_in'  : line.split()[3],
                'pkts_out' : line.split()[5],

                # convert raw byte number to something more human readable
                # Note: could be replaced by Python3 hurry.filesize module
                'bytes_in' : byte_string( line.split()[2] ),
                'bytes_out': byte_string( line.split()[4] ),

                # convert IP address from hex 'FE000A0A' to decimal '4261415434'
                'loc'      : kernel2ip( line.split()[7] ),
            }
            result['data'].append(data)

    return result

def do_mr_mfc():
    """
    Read contents of file /proc/net/ip_mr_cache and print a more human
    friendly version to the command line. IPv4 addresses present as
    32bit integers in hex format are converted to IPv4 notation, too.
    """

    with open('/proc/net/ip_mr_cache', 'r') as f:
        lines = len(f.readlines())
        if lines < 2:
            return None

    # We need this to convert from interface index to a real interface name
    # Thus we also skip the format identifier on list index 0
    vif = do_mr_vif()['data'][1:]

    result = {
        'data': []
    }

    # Build up table format string
    table_format = {
        'group' : 'Group',
        'origin': 'Origin',
        'iif'   : 'In',
        'oifs'  : ['Out'],
        'pkts'  : 'Pkts',
        'bytes' : 'Bytes',
        'wrong' : 'Wrong'
    }
    result['data'].append(table_format)

    # read and parse information from /proc filesystem
    with open('/proc/net/ip_mr_cache', 'r') as f:
        header_line = next(f)
        for line in f:
            data = {
                # convert IP address from hex 'FE000A0A' to decimal '4261415434'
                'group' : kernel2ip( line.split()[0] ),
                'origin': kernel2ip( line.split()[1] ),

                'iif'   : '--',
                'pkts'  : '',
                'bytes' : '',
                'wrong' : '',
                'oifs'  : []
            }

            iif = int( line.split()[2] )
            if not ((iif == -1) or (iif == 65535)):
                data['pkts']  = line.split()[3]
                data['bytes'] = byte_string( line.split()[4] )
                data['wrong'] = line.split()[5]

                # convert index to real interface name
                data['iif']  = vif[iif]['interface']

                # convert each output interface index to a real interface name
                for oif in line.split()[6:]:
                    idx = int( oif.split(':')[0] )
                    data['oifs'].append( vif[idx]['interface'] )

            result['data'].append(data)

    return result

if __name__ == '__main__':
    args = parser.parse_args()

    # Do nothing if service is not configured
    c = vyos.config.Config()
    if not c.exists_effective('protocols igmp-proxy'):
        print("IGMP proxy is not configured")
        sys.exit(0)

    if args.interface:
        data = do_mr_vif()
        if data:
            tmpl = jinja2.Template(vif_out_tmpl)
            print(tmpl.render(data))

        sys.exit(0)
    elif args.mfc:
        data = do_mr_mfc()
        if data:
            tmpl = jinja2.Template(mfc_out_tmpl)
            print(tmpl.render(data))

        sys.exit(0)
    else:
        parser.print_help()
        sys.exit(1)

