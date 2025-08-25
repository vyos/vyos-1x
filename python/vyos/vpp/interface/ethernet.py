# VyOS implementation of VPP Ethernet interface
#
# Copyright (C) VyOS Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from vyos.vpp import VPPControl


class EthernetInterface:
    """Interface Ethernet"""

    def __init__(self, ifname, kernel_interface: str = ''):
        self.instance = int(ifname.removeprefix('eth'))
        self.ifname = ifname
        self.kernel_interface = kernel_interface
        self.vpp = VPPControl()

    def add(self):
        pass

    def delete(self):
        pass

    def kernel_add(self):
        """Add LCP pair
        Example:
            from vyos.vpp.interface import EthernetInterface
            a = EthernetInterface(ifname='eth0')
            a.kernel_add()
        """
        self.vpp.lcp_pair_add(self.ifname, self.kernel_interface)

    def kernel_delete(self):
        """Delete LCP pair
        Example:
            from vyos.vpp.interface import EthernetInterface
            a = EthernetInterface(ifname='eth0')
            a.kernel_delete()
        """
        self.vpp.lcp_pair_del(self.ifname, self.kernel_interface)
