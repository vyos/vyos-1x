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

from enum import IntEnum

class IFlag(IntEnum):
    """ net/if.h interface flags """

    IFF_UP = 0x1            #: Interface up/down status
    IFF_BROADCAST = 0x2     #: Broadcast address valid
    IFF_DEBUG = 0x4,        #: Debugging
    IFF_LOOPBACK = 0x8      #: Is loopback network
    IFF_POINTOPOINT = 0x10  #: Is point-to-point link
    IFF_NOTRAILERS = 0x20   #: Avoid use of trailers
    IFF_RUNNING = 0x40      #: Resources allocated
    IFF_NOARP = 0x80        #: No address resolution protocol
    IFF_PROMISC = 0x100     #: Promiscuous mode
    IFF_ALLMULTI = 0x200    #: Receive all multicast
    IFF_MASTER = 0x400      #: Load balancer master
    IFF_SLAVE = 0x800       #: Load balancer slave
    IFF_MULTICAST = 0x1000  #: Supports multicast
    IFF_PORTSEL = 0x2000    #: Media type adjustable
    IFF_AUTOMEDIA = 0x4000  #: Automatic media type enabled
    IFF_DYNAMIC = 0x8000    #: Is a dial-up device with dynamic address
