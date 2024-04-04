# Copyright 2019-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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
import socket
import fcntl
import struct

SIOCGIFFLAGS = 0x8913

def get_terminal_size():
    """ pull the terminal size """
    """ rows,cols = vyos.ioctl.get_terminal_size() """
    columns, rows = os.get_terminal_size(0)
    return (rows,columns)

def get_interface_flags(intf):
    """ Pull the SIOCGIFFLAGS """
    nullif = '\0'*256
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    raw = fcntl.ioctl(sock.fileno(), SIOCGIFFLAGS, intf + nullif)
    flags, = struct.unpack('H', raw[16:18])
    return flags
