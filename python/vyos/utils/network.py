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

import os

def get_protocol_by_name(protocol_name):
    """Get protocol number by protocol name

       % get_protocol_by_name('tcp')
       % 6
    """
    import socket
    try:
        protocol_number = socket.getprotobyname(protocol_name)
        return protocol_number
    except socket.error:
        return protocol_name

def interface_exists_in_netns(interface_name, netns):
    from vyos.util import rc_cmd
    rc, out = rc_cmd(f'ip netns exec {netns} ip link show dev {interface_name}')
    if rc == 0:
        return True
    return False
